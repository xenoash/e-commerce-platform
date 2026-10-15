import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.carts.models import Cart
from apps.catalog.models import Product
from apps.payments.base import PaymentResult, PaymentStatus
from apps.payments.models import Payment
from apps.promotions.services import reclaim_coupon, release_coupon
from apps.tenancy.context import current_store_id

from .models import Order

logger = logging.getLogger(__name__)


def reserve_stock(lines):
    shortages = []
    for line in sorted(lines, key=lambda line: str(line["product_id"])):
        if not line["track_stock"]:
            continue
        reserved = Product.objects.filter(pk=line["product_id"], is_active=True, stock__gte=line["quantity"]).update(
            stock=F("stock") - line["quantity"]
        )
        if not reserved:
            product = Product.objects.filter(pk=line["product_id"]).first()
            shortages.append(
                {
                    "item_id": line.get("item_id"),
                    "product_id": str(line["product_id"]),
                    "requested": line["quantity"],
                    "available": product.stock if product and product.is_active else 0,
                }
            )
    return shortages


def restock(order):
    for line in sorted(order.lines.filter(track_stock=True), key=lambda line: str(line.product_id)):
        if line.product_id:
            Product.objects.filter(pk=line.product_id).update(stock=F("stock") + line.quantity)


def _transition_order(order, sources, target, **fields):
    updated = Order.objects.filter(pk=order.pk, status__in=sources).update(
        status=target, updated_at=timezone.now(), **fields
    )
    if updated:
        order.status = target
        for name, value in fields.items():
            setattr(order, name, value)
    return bool(updated)


def _transition_payment(payment, target, **fields):
    updated = Payment.objects.filter(pk=payment.pk, status__in=Payment.sources_for(target)).update(
        status=target, updated_at=timezone.now(), **fields
    )
    if updated:
        payment.status = target
    return bool(updated)


def _set_cart_status(cart_id, sources, target):
    if cart_id is None:
        return
    Cart.objects.filter(pk=cart_id, status__in=sources).update(status=target, version=F("version") + 1)


def schedule_invoice(order):
    from apps.invoicing.tasks import issue_invoice

    store_id = str(current_store_id())
    order_id = str(order.pk)
    transaction.on_commit(lambda: issue_invoice.delay(order_id, store_id=store_id), robust=True)


def schedule_refund(payment):
    from .tasks import refund_payment

    store_id = str(current_store_id())
    payment_id = str(payment.pk)
    transaction.on_commit(lambda: refund_payment.delay(payment_id, store_id=store_id), robust=True)


def release_order(order):
    restock(order)
    release_coupon(order)
    _set_cart_status(order.cart_id, [Cart.Status.CHECKING_OUT], Cart.Status.OPEN)


def _lock_for_settlement(payment_id):
    payment = Payment.objects.select_related("order").get(pk=payment_id)
    cart_id = payment.order.cart_id
    if cart_id is not None:
        Cart.objects.select_for_update(of=("self",)).filter(pk=cart_id).first()
    order = Order.objects.select_for_update(of=("self",)).get(pk=payment.order_id)
    payment = Payment.objects.select_for_update(of=("self",)).get(pk=payment_id)
    return order, payment


def _try_revive(order):
    lines = [
        {"product_id": line.product_id, "quantity": line.quantity, "track_stock": line.track_stock}
        for line in order.lines.all()
        if line.product_id
    ]
    with transaction.atomic():
        shortages = reserve_stock(lines)
        if shortages or not reclaim_coupon(order):
            transaction.set_rollback(True)
            return False
    return True


def apply_payment_result(payment_id, result: PaymentResult):
    with transaction.atomic():
        order, payment = _lock_for_settlement(payment_id)
        external = {"external_ref": result.external_ref} if result.external_ref else {}

        if result.status == PaymentStatus.SUCCEEDED:
            if not _transition_payment(
                payment, Payment.Status.SUCCEEDED, settled_at=timezone.now(), next_action=None, **external
            ):
                return order
            now = timezone.now()
            if _transition_order(order, [Order.Status.PENDING_PAYMENT], Order.Status.PAID, paid_at=now):
                _set_cart_status(order.cart_id, [Cart.Status.CHECKING_OUT], Cart.Status.CONVERTED)
                schedule_invoice(order)
            elif order.status in Order.CLOSED_UNPAID_STATUSES:
                if _try_revive(order):
                    _transition_order(order, Order.CLOSED_UNPAID_STATUSES, Order.Status.PAID, paid_at=now)
                    schedule_invoice(order)
                    logger.warning("late_payment_honoured order=%s", order.pk)
                else:
                    _transition_order(order, Order.CLOSED_UNPAID_STATUSES, Order.Status.NEEDS_ATTENTION)
                    schedule_refund(payment)
                    logger.error("late_payment_refunded order=%s", order.pk)
            return order

        if result.status == PaymentStatus.DEFERRED:
            if _transition_payment(payment, Payment.Status.DEFERRED, **external) and _transition_order(
                order, [Order.Status.PENDING_PAYMENT], Order.Status.CONFIRMED
            ):
                _set_cart_status(order.cart_id, [Cart.Status.CHECKING_OUT], Cart.Status.CONVERTED)
                schedule_invoice(order)
            return order

        if result.status == PaymentStatus.REQUIRES_ACTION:
            _transition_payment(payment, Payment.Status.REQUIRES_ACTION, next_action=result.next_action, **external)
            return order

        if result.status == PaymentStatus.PENDING:
            _transition_payment(payment, Payment.Status.PENDING, **external)
            return order

        failed = _transition_payment(
            payment,
            Payment.Status.FAILED,
            failure_code=result.failure_code[:64],
            failure_message=result.failure_message[:255],
            next_action=None,
            **external,
        )
        if failed and _transition_order(order, [Order.Status.PENDING_PAYMENT], Order.Status.PAYMENT_FAILED):
            release_order(order)
        return order


def _lock_order(order_id):
    cart_id = Order.objects.filter(pk=order_id).values_list("cart_id", flat=True).first()
    if cart_id is not None:
        Cart.objects.select_for_update(of=("self",)).filter(pk=cart_id).first()
    return Order.objects.select_for_update(of=("self",)).get(pk=order_id)


def expire_order(order_id):
    with transaction.atomic():
        order = _lock_order(order_id)
        if not _transition_order(order, [Order.Status.PENDING_PAYMENT], Order.Status.EXPIRED):
            return False
        for payment in order.payments.filter(status__in=Payment.OPEN_STATUSES):
            _transition_payment(payment, Payment.Status.CANCELLED, next_action=None)
        release_order(order)
        return True
