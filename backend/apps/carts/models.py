from django.db import models
from django.db.models import Q

from apps.tenancy.models import TenantModel


class Cart(TenantModel):
    class Status(models.TextChoices):
        OPEN = "open"
        CHECKING_OUT = "checking_out"
        CONVERTED = "converted"
        ABANDONED = "abandoned"

    customer = models.ForeignKey(
        "customers.Customer", null=True, blank=True, on_delete=models.SET_NULL, related_name="carts"
    )
    token_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    version = models.PositiveIntegerField(default=1)
    coupon = models.ForeignKey("promotions.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    shipping_address = models.JSONField(null=True, blank=True)
    billing_address = models.JSONField(null=True, blank=True)
    payment_method = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "customer"],
                condition=Q(status__in=["open", "checking_out"], customer__isnull=False),
                name="one_active_cart_per_customer",
            ),
            models.CheckConstraint(condition=Q(customer__isnull=False) | ~Q(token_hash=""), name="cart_has_owner"),
        ]

    ACTIVE_STATUSES = (Status.OPEN, Status.CHECKING_OUT)

    @property
    def is_open(self):
        return self.status == self.Status.OPEN


class CartItem(TenantModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveSmallIntegerField()
    unit_price_seen = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="one_line_per_product"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="cart_item_quantity_positive"),
        ]
