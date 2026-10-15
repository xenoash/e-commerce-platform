from django.db import models
from django.db.models import Q

from apps.tenancy.models import TenantModel

from .zatca.signing import FIRST_PREVIOUS_HASH


class EgsDevice(TenantModel):
    class Environment(models.TextChoices):
        FAKE = "fake"
        DEVELOPER_PORTAL = "developer_portal"
        SIMULATION = "simulation"
        PRODUCTION = "production"

    name = models.CharField(max_length=80)
    serial_number = models.CharField(max_length=120)
    environment = models.CharField(max_length=20, choices=Environment.choices, default=Environment.FAKE)
    private_key_pem = models.TextField()
    certificate_b64 = models.TextField()
    binary_security_token = models.TextField(blank=True)
    api_secret = models.TextField(blank=True)
    last_icv = models.PositiveBigIntegerField(default=0)
    last_invoice_hash = models.TextField(default=FIRST_PREVIOUS_HASH)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store"], condition=Q(is_active=True), name="one_active_egs_per_store"),
        ]


class Invoice(TenantModel):
    class DocType(models.TextChoices):
        INVOICE = "invoice"
        CREDIT_NOTE = "credit_note"

    class Kind(models.TextChoices):
        SIMPLIFIED = "simplified"
        STANDARD = "standard"

    class Status(models.TextChoices):
        ISSUED = "issued"
        PENDING_RETRY = "pending_retry"
        REPORTED = "reported"
        CLEARED = "cleared"
        REJECTED = "rejected"

    ACCEPTED_STATUSES = (Status.REPORTED, Status.CLEARED)
    SUBMITTABLE_STATUSES = (Status.ISSUED, Status.PENDING_RETRY)

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="invoices")
    device = models.ForeignKey(EgsDevice, on_delete=models.PROTECT, related_name="invoices")
    doc_type = models.CharField(max_length=16, choices=DocType.choices, default=DocType.INVOICE)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    number = models.CharField(max_length=40)
    uuid = models.UUIDField()
    icv = models.PositiveBigIntegerField()
    pih = models.TextField()
    invoice_hash = models.TextField()
    issued_at = models.DateTimeField()
    signed_xml = models.TextField()
    qr_base64 = models.TextField()
    cleared_xml = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ISSUED)
    submission_attempts = models.PositiveIntegerField(default=0)
    zatca_status = models.CharField(max_length=32, blank=True)
    zatca_warnings = models.JSONField(default=list, blank=True)
    zatca_errors = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    billing_reference = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="credit_notes"
    )
    reason = models.CharField(max_length=200, blank=True)
    seller = models.JSONField()
    buyer = models.JSONField()
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    vat_total = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["icv"]
        constraints = [
            models.UniqueConstraint(fields=["order", "doc_type"], name="one_document_per_order_and_type"),
            models.UniqueConstraint(fields=["device", "icv"], name="icv_unique_per_device"),
            models.UniqueConstraint(fields=["store", "number"], name="invoice_number_unique_per_store"),
        ]
        indexes = [models.Index(fields=["status", "issued_at"], name="invoice_status_issued")]

    IMMUTABLE_FIELDS = ("icv", "pih", "invoice_hash", "signed_xml", "uuid", "number", "device_id")

    def save(self, *args, **kwargs):
        if self._state.adding is False and self.pk:
            original = Invoice.unscoped.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).first()
            if original and any(original[name] != getattr(self, name) for name in self.IMMUTABLE_FIELDS):
                raise ValueError("A signed invoice cannot be changed; issue a credit note instead.")
        super().save(*args, **kwargs)

    def document_xml(self):
        return self.cleared_xml or self.signed_xml
