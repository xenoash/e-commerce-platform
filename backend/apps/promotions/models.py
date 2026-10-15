from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from apps.tenancy.models import TenantModel


class Coupon(TenantModel):
    class Kind(models.TextChoices):
        PERCENT = "percent"
        FIXED = "fixed"
        FREE_SHIPPING = "free_shipping"

    code = models.CharField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    per_customer_limit = models.PositiveIntegerField(null=True, blank=True)
    applies_to_product_ids = models.JSONField(default=list, blank=True)
    rules = models.JSONField(default=list, blank=True)
    advertise = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("code"), "store", name="coupon_code_unique_per_store"),
            models.CheckConstraint(
                condition=Q(usage_limit__isnull=True) | Q(times_used__lte=F("usage_limit")),
                name="coupon_usage_within_limit",
            ),
            models.CheckConstraint(
                condition=~Q(kind="percent") | Q(value__gt=0, value__lte=100), name="coupon_percent_range"
            ),
            models.CheckConstraint(condition=Q(value__gte=0), name="coupon_value_not_negative"),
        ]

    def __str__(self):
        return self.code


class CouponRedemption(TenantModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="coupon_redemption")
    customer = models.ForeignKey("customers.Customer", null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["store", "coupon", "customer"], name="redemption_coupon_customer")]
