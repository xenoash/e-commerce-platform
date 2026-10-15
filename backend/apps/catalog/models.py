from django.db import models
from django.db.models import F, Q

from apps.tenancy.models import TenantModel


class Product(TenantModel):
    class Kind(models.TextChoices):
        PHYSICAL = "physical"
        DIGITAL = "digital"
        SERVICE = "service"

    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PHYSICAL)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    track_stock = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)
    max_per_order = models.PositiveSmallIntegerField(default=20)
    is_addon = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["store", "sku"], name="product_sku_unique_per_store"),
            models.CheckConstraint(condition=Q(price__gte=0), name="product_price_not_negative"),
            models.CheckConstraint(condition=Q(stock__gte=0), name="product_stock_not_negative"),
            models.CheckConstraint(condition=Q(max_per_order__gte=1), name="product_max_per_order_positive"),
        ]
        indexes = [models.Index(fields=["store", "is_active", "name"], name="product_store_active_name")]

    def __str__(self):
        return self.sku

    @property
    def in_stock(self):
        return not self.track_stock or self.stock > 0


class ProductRecommendation(TenantModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="recommendations")
    recommended = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)
    headline = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["store", "product", "recommended"], name="recommendation_unique"),
            models.CheckConstraint(condition=~Q(product=F("recommended")), name="recommendation_not_self"),
        ]
