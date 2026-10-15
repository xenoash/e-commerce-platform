from django.db import models

from apps.tenancy.models import TenantModel


class IdempotencyRecord(TenantModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"

    scope = models.CharField(max_length=32)
    resource_id = models.CharField(max_length=64)
    key = models.CharField(max_length=255)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    order_id = models.UUIDField(null=True, blank=True)
    locked_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "scope", "resource_id", "key"], name="idempotency_key_unique_per_resource"
            ),
        ]
        indexes = [models.Index(fields=["created_at"], name="idempotency_created")]
