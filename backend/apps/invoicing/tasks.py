import logging
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.orders.models import Order
from apps.tenancy.context import rls_bypass, tenant_context
from apps.tenancy.models import Store
from apps.tenancy.tasks import tenant_task

from . import services
from .models import Invoice

logger = logging.getLogger(__name__)

SWEEP_GRACE = timedelta(minutes=5)
SWEEP_BATCH = 200
RETRY_SCHEDULE_SECONDS = (30, 120, 600, 1800, 3600)


@tenant_task(bind=True, max_retries=3, default_retry_delay=30)
def issue_invoice(self, order_id):
    order = Order.objects.get(pk=order_id)
    invoice, _ = services.issue_invoice(order)
    return str(invoice.pk) if invoice else None


@tenant_task(bind=True, max_retries=len(RETRY_SCHEDULE_SECONDS))
def submit_invoice(self, invoice_id):
    invoice = Invoice.objects.select_related("device", "billing_reference").get(pk=invoice_id)
    status = services.submit(invoice)
    if status in (Invoice.Status.PENDING_RETRY, "awaiting_original") and self.request.retries < self.max_retries:
        raise self.retry(countdown=RETRY_SCHEDULE_SECONDS[self.request.retries])
    return status


def _group_by_store(rows):
    grouped = defaultdict(list)
    for store_id, object_id in rows:
        grouped[store_id].append(object_id)
    return grouped


@shared_task
def sweep_uninvoiced_orders():
    cutoff = timezone.now() - SWEEP_GRACE
    with rls_bypass():
        rows = list(
            Order.objects.filter(status__in=Order.FULFILLABLE_STATUSES, updated_at__lte=cutoff)
            .exclude(invoices__doc_type=Invoice.DocType.INVOICE)
            .values_list("store_id", "id")[:SWEEP_BATCH]
        )
    issued = 0
    for store in Store.objects.filter(pk__in=_group_by_store(rows)):
        with tenant_context(store):
            for order in Order.objects.filter(pk__in=_group_by_store(rows)[store.pk]):
                try:
                    _, created = services.issue_invoice(order)
                    issued += int(created)
                except Exception:
                    logger.exception("invoice_sweep_failed order=%s", order.pk)
    return issued


@shared_task
def submit_due_invoices():
    cutoff = timezone.now() - SWEEP_GRACE
    with rls_bypass():
        rows = list(
            Invoice.objects.filter(status__in=Invoice.SUBMITTABLE_STATUSES, issued_at__lte=cutoff)
            .order_by("device_id", "icv")
            .values_list("store_id", "id")[:SWEEP_BATCH]
        )
    outcomes = defaultdict(int)
    grouped = _group_by_store(rows)
    for store in Store.objects.filter(pk__in=grouped):
        with tenant_context(store):
            for invoice in (
                Invoice.objects.select_related("device", "billing_reference")
                .filter(pk__in=grouped[store.pk])
                .order_by("icv")
            ):
                outcomes[str(services.submit(invoice))] += 1
    return dict(outcomes)
