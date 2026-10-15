from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.tenancy.context import rls_bypass

from .models import IdempotencyRecord


@shared_task
def purge_idempotency_records():
    cutoff = timezone.now() - timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)
    with rls_bypass():
        deleted, _ = IdempotencyRecord.objects.filter(created_at__lt=cutoff).delete()
    return deleted
