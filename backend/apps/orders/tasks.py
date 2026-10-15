import logging
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.payments.base import GatewayError
from apps.payments.models import Payment
from apps.payments.registry import gateway_for
from apps.tenancy.context import current_store, rls_bypass, tenant_context
from apps.tenancy.models import Store
from apps.tenancy.tasks import tenant_task

from .lifecycle import apply_payment_result, expire_order
from .models import Order

logger = logging.getLogger(__name__)

RECONCILE_AFTER = timedelta(minutes=2)
SWEEP_BATCH = 500


def reconcile_order(order):
    payment = order.payments.filter(status__in=Payment.OPEN_STATUSES).order_by("-created_at").first()
    if payment is not None:
        gateway = gateway_for(current_store(), order.store_payment_method(payment.gateway))
        try:
            result = gateway.retrieve(str(payment.pk), payment.external_ref)
        except GatewayError as exc:
            logger.warning("reconcile_failed order=%s transient=%s", order.pk, exc.transient)
            result = None
        if result is not None:
            order = apply_payment_result(payment.pk, result)
    if order.status == Order.Status.PENDING_PAYMENT and order.expires_at and order.expires_at <= timezone.now():
        expire_order(order.pk)
        return "expired"
    return order.status


@shared_task
def sweep_pending_orders():
    now = timezone.now()
    with rls_bypass():
        due = list(
            Order.objects.filter(status=Order.Status.PENDING_PAYMENT, placed_at__lte=now - RECONCILE_AFTER)
            .order_by("placed_at")
            .values_list("store_id", "id")[:SWEEP_BATCH]
        )
    by_store = defaultdict(list)
    for store_id, order_id in due:
        by_store[store_id].append(order_id)
    outcomes = defaultdict(int)
    for store in Store.objects.filter(pk__in=by_store):
        with tenant_context(store):
            for order in Order.objects.filter(pk__in=by_store[store.pk]):
                try:
                    outcomes[reconcile_order(order)] += 1
                except Exception:
                    logger.exception("sweep_order_failed order=%s", order.pk)
                    outcomes["error"] += 1
    return dict(outcomes)


@tenant_task(bind=True, max_retries=5, default_retry_delay=60)
def refund_payment(self, payment_id):
    payment = Payment.objects.select_related("order").get(pk=payment_id)
    if payment.status != Payment.Status.SUCCEEDED:
        return payment.status
    gateway = gateway_for(current_store(), payment.order.store_payment_method(payment.gateway))
    try:
        result = gateway.refund(str(payment.pk), payment.amount)
    except GatewayError as exc:
        if exc.transient:
            raise self.retry(exc=exc) from exc
        raise
    if result.succeeded:
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.SUCCEEDED).update(status=Payment.Status.REFUNDED)
    return result.succeeded
