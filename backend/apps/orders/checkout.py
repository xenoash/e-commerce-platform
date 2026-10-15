import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.carts.models import Cart
from apps.carts.services import build_cart_view, load_cart
from apps.common import idempotency
from apps.common.errors import ErrorCode, Problem
from apps.common.money import format_amount
from apps.payments.base import GatewayError, PaymentRequest, PaymentResult, PaymentStatus
from apps.payments.models import Payment
from apps.payments.registry import gateway_for
from apps.promotions.services import redeem_coupon
from apps.tenancy.context import current_store

from .lifecycle import apply_payment_result, reserve_stock
from .models import Order, OrderLine

logger = logging.getLogger(__name__)

CHECKOUT_SCOPE = "checkout"


@dataclass(frozen=True)
class CheckoutInput:
    payment_token: str | None = None
    expected_total: Decimal | None = None
    po_number: str = ""


@dataclass(frozen=True)
class CheckoutOutcome:
    order: Order
    status_code: int
    replayed: bool = False


def _buyer_snapshot(cart):
    billing = cart.billing_address or {}
    shipping = cart.shipping_address or {}
    customer = cart.customer
    contact = billing or shipping
    return {
        "kind": customer.kind if customer else "individual",
        "customer_id": str(customer.pk) if customer else None,
        "name": (customer.name if customer else "") or contact.get("name", ""),
        "email": (customer.email if customer else "") or contact.get("email", ""),
        "phone": contact.get("phone", ""),
        "company_name": billing.get("company_name") or (customer.company_name if customer else ""),
        "vat_number": billing.get("vat_number") or (customer.vat_number if customer else ""),
        "cr_number": billing.get("cr_number") or (customer.cr_number if customer else ""),
    }


def _assert_checkout_ready(view, expected_total):
    if any(entry["reason"] == "discontinued" for entry in view.unavailable):
        raise Problem(409, ErrorCode.ITEM_UNAVAILABLE, "Some items are no longer sold.", items=view.unavailable)
    if view.unavailable:
        raise Problem(
            409, ErrorCode.OUT_OF_STOCK, "Some items sold out while you were checking out.", items=view.unavailable
        )
    if view.coupon is not None and not view.coupon.applicable:
        raise Problem(
            409,
            ErrorCode.COUPON_NOT_APPLICABLE,
            view.coupon.problem.detail or "The coupon no longer applies to this cart.",
            reason=str(view.coupon.problem.code),
            **view.coupon.problem.extra,
        )
    if not view.items:
        raise Problem(409, ErrorCode.CART_EMPTY, "Add at least one item before checking out.")
    if view.missing:
        raise Problem(
            409, ErrorCode.CART_NOT_READY, "The cart is missing details needed to check out.", missing=view.missing
        )
    if expected_total is not None and expected_total != view.priced.total:
        raise Problem(
            409,
            ErrorCode.CART_TOTAL_CHANGED,
            "The cart total changed since you last saw it. Review the cart and confirm again.",
            expected_total=format_amount(expected_total),
            current_total=format_amount(view.priced.total),
        )


def _create_order(cart, view, data, gateway):
    store = current_store()
    priced = view.priced
    line_rows = []
    for position, item in enumerate(view.items, start=1):
        priced_line = priced.line(str(item.pk))
        line_rows.append(
            {
                "item_id": str(item.pk),
                "product": item.product,
                "product_id": item.product_id,
                "position": position,
                "quantity": item.quantity,
                "track_stock": item.product.track_stock,
                "priced": priced_line,
            }
        )
    shortages = reserve_stock(line_rows)
    if shortages:
        raise Problem(409, ErrorCode.OUT_OF_STOCK, "Some items sold out while you were checking out.", items=shortages)

    order = Order.objects.create(
        number=Order.next_number(),
        cart=cart,
        customer=cart.customer,
        token_hash=cart.token_hash,
        currency=store.currency,
        prices_include_vat=priced.prices_include_vat,
        vat_rate=priced.vat_rate,
        subtotal=priced.subtotal,
        item_discount=priced.item_discount,
        shipping_fee=priced.shipping.subtotal,
        shipping_discount=priced.shipping_discount,
        shipping_net=priced.shipping.net,
        shipping_vat=priced.shipping.vat,
        taxable_amount=priced.taxable_amount,
        vat_total=priced.vat,
        total=priced.total,
        coupon=view.coupon.coupon if view.coupon else None,
        coupon_code=view.coupon.coupon.code if view.coupon else "",
        buyer=_buyer_snapshot(cart),
        shipping_address=cart.shipping_address,
        billing_address=cart.billing_address,
        po_number=data.po_number,
        payment_method=view.payment_method.method,
        payment_gateway=view.payment_method.gateway,
        invoice_kind=view.invoice_kind,
        expires_at=timezone.now() + timedelta(minutes=settings.ORDER_PAYMENT_HOLD_MINUTES),
    )
    OrderLine.objects.bulk_create(
        [
            OrderLine(
                store_id=store.pk,
                order=order,
                product_id=row["product_id"],
                position=row["position"],
                sku=row["product"].sku,
                name=row["product"].name,
                name_ar=row["product"].name_ar,
                kind=row["product"].kind,
                track_stock=row["track_stock"],
                quantity=row["quantity"],
                unit_price=row["priced"].unit_price,
                subtotal=row["priced"].subtotal,
                discount=row["priced"].discount,
                net=row["priced"].net,
                vat_rate=priced.vat_rate,
                vat=row["priced"].vat,
                total=row["priced"].total,
            )
            for row in line_rows
        ]
    )
    if view.coupon is not None:
        redeem_coupon(view.coupon.coupon, order=order, customer=cart.customer, amount=priced.discount)
    gateway.reserve_in_transaction(order, cart.customer)
    payment = Payment.objects.create(
        order=order,
        gateway=view.payment_method.gateway,
        method=view.payment_method.method,
        amount=order.total,
        currency=order.currency,
    )
    return order, payment


def _payment_request(order, payment, token):
    store = current_store()
    return PaymentRequest(
        reference=str(payment.pk),
        amount=payment.amount,
        currency=payment.currency,
        method=payment.method,
        description=f"{store.name} order {order.display_number}",
        return_url=f"{settings.STOREFRONT_URL}/{store.handle}/orders/{order.pk}",
        webhook_url=f"{settings.INTERNAL_API_URL}/api/v1/webhooks/payments/{payment.gateway}/{store.handle}",
        token=token,
        customer_email=order.buyer.get("email") or None,
        metadata={"order_id": str(order.pk), "order_number": order.display_number, "store": store.handle},
    )


def collect_payment(order, payment, token):
    store = current_store()
    method_config = order.store_payment_method()
    gateway = gateway_for(store, method_config)
    try:
        result = gateway.create_payment(_payment_request(order, payment, token))
    except GatewayError as exc:
        logger.warning("gateway_error order=%s transient=%s error=%s", order.pk, exc.transient, exc)
        if exc.transient:
            result = PaymentResult(PaymentStatus.PENDING)
        else:
            result = PaymentResult(PaymentStatus.FAILED, failure_code="gateway_rejected", failure_message=str(exc))
    return apply_payment_result(payment.pk, result)


def checkout(request, cart_id, data: CheckoutInput):
    key = idempotency.require_key(request)
    cart = load_cart(request, cart_id)
    fingerprint = idempotency.fingerprint(
        str(cart.pk),
        str(cart.customer_id or ""),
        data.payment_token,
        str(data.expected_total) if data.expected_total is not None else None,
        data.po_number,
    )
    claim = idempotency.claim(scope=CHECKOUT_SCOPE, resource_id=cart.pk, key=key, request_fingerprint=fingerprint)
    if claim.state == idempotency.ClaimState.REPLAY:
        return CheckoutOutcome(
            order=Order.objects.get(pk=claim.record.order_id),
            status_code=claim.record.response_status or 200,
            replayed=True,
        )

    if claim.record.order_id:
        order = Order.objects.get(pk=claim.record.order_id)
        payment = order.payments.order_by("-created_at").first()
        if payment.status == Payment.Status.INITIATED:
            order = collect_payment(order, payment, data.payment_token)
        idempotency.complete(claim.record, response_status=201, order_id=order.pk)
        return CheckoutOutcome(order=order, status_code=201)

    try:
        with transaction.atomic():
            cart = load_cart(request, cart_id, lock=True)
            if cart.status == Cart.Status.CHECKING_OUT:
                pending = cart.orders.filter(status=Order.Status.PENDING_PAYMENT).first()
                if pending is not None:
                    idempotency.complete(claim.record, response_status=200, order_id=pending.pk)
                    return CheckoutOutcome(order=pending, status_code=200)
            if cart.status != Cart.Status.OPEN:
                raise Problem(409, ErrorCode.CART_NOT_OPEN, f"The cart is {cart.status} and cannot be checked out.")
            view = build_cart_view(cart)
            _assert_checkout_ready(view, data.expected_total)
            gateway = gateway_for(current_store(), view.payment_method)
            if gateway.requires_token and not data.payment_token:
                raise Problem(422, ErrorCode.PAYMENT_TOKEN_REQUIRED, "Send a payment_token for this payment method.")
            problem = gateway.eligibility_problem(cart.customer, view.priced.total)
            if problem is not None:
                raise problem
            order, payment = _create_order(cart, view, data, gateway)
            Cart.objects.filter(pk=cart.pk).update(status=Cart.Status.CHECKING_OUT, version=cart.version + 1)
            idempotency.attach_order(claim.record, order.pk)
    except Problem:
        idempotency.release(claim.record)
        raise

    order = collect_payment(order, payment, data.payment_token)
    idempotency.complete(claim.record, response_status=201, order_id=order.pk)
    return CheckoutOutcome(order=order, status_code=201)


def confirm_payment(order):
    payment = order.payments.filter(status__in=Payment.OPEN_STATUSES).order_by("-created_at").first()
    if payment is None:
        return order
    gateway = gateway_for(current_store(), order.store_payment_method())
    try:
        result = gateway.retrieve(str(payment.pk), payment.external_ref)
    except GatewayError as exc:
        if exc.transient:
            return order
        raise
    return apply_payment_result(payment.pk, result)
