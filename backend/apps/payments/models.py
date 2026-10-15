from django.db import models
from django.db.models import Q

from apps.tenancy.models import TenantModel


class StorePaymentMethod(TenantModel):
    class Method(models.TextChoices):
        CARD = "card"
        APPLE_PAY = "apple_pay"
        COD = "cod"
        NET_TERMS = "net_terms"

    method = models.CharField(max_length=32, choices=Method.choices)
    gateway = models.CharField(max_length=32)
    display_name = models.CharField(max_length=80)
    is_enabled = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position", "method"]
        constraints = [models.UniqueConstraint(fields=["store", "method"], name="payment_method_unique_per_store")]


class Payment(TenantModel):
    class Status(models.TextChoices):
        INITIATED = "initiated"
        REQUIRES_ACTION = "requires_action"
        PENDING = "pending"
        SUCCEEDED = "succeeded"
        DEFERRED = "deferred"
        FAILED = "failed"
        CANCELLED = "cancelled"
        REFUNDED = "refunded"

    TRANSITIONS = {
        Status.INITIATED: {
            Status.REQUIRES_ACTION,
            Status.PENDING,
            Status.SUCCEEDED,
            Status.DEFERRED,
            Status.FAILED,
            Status.CANCELLED,
        },
        Status.REQUIRES_ACTION: {Status.PENDING, Status.SUCCEEDED, Status.FAILED, Status.CANCELLED},
        Status.PENDING: {Status.REQUIRES_ACTION, Status.SUCCEEDED, Status.FAILED, Status.CANCELLED},
        Status.CANCELLED: {Status.SUCCEEDED},
        Status.FAILED: set(),
        Status.SUCCEEDED: {Status.REFUNDED},
        Status.DEFERRED: {Status.SUCCEEDED, Status.CANCELLED},
        Status.REFUNDED: set(),
    }
    OPEN_STATUSES = (Status.INITIATED, Status.REQUIRES_ACTION, Status.PENDING)

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField(max_length=32)
    method = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    external_ref = models.CharField(max_length=128, blank=True)
    next_action = models.JSONField(null=True, blank=True)
    failure_code = models.CharField(max_length=64, blank=True)
    failure_message = models.CharField(max_length=255, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.id

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "gateway", "external_ref"],
                condition=~Q(external_ref=""),
                name="payment_external_ref_unique",
            ),
            models.CheckConstraint(condition=Q(amount__gte=0), name="payment_amount_not_negative"),
        ]
        indexes = [models.Index(fields=["status", "created_at"], name="payment_status_created")]

    @classmethod
    def sources_for(cls, target):
        return [source for source, targets in cls.TRANSITIONS.items() if target in targets]


class WebhookEvent(TenantModel):
    gateway = models.CharField(max_length=32)
    event_id = models.CharField(max_length=128)
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.SET_NULL)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "gateway", "event_id"], name="webhook_event_unique"),
        ]


class SimulatedCharge(models.Model):
    class Status(models.TextChoices):
        REQUIRES_ACTION = "requires_action"
        SUCCEEDED = "succeeded"
        FAILED = "failed"
        CANCELLED = "cancelled"
        REFUNDED = "refunded"

    id = models.CharField(primary_key=True, max_length=40)
    store_id = models.UUIDField()
    store_handle = models.CharField(max_length=63)
    reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    token = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices)
    failure_code = models.CharField(max_length=64, blank=True)
    return_url = models.URLField(max_length=500)
    webhook_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.id
