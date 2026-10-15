from decimal import Decimal
from uuid import uuid7

from django.db import models

from apps.common import validators

from .context import CrossTenantWrite, TenantNotSet, bypass_active, current_store_id, current_store_id_or_none


class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    handle = models.SlugField(max_length=63, unique=True)
    name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=120)
    vat_number = models.CharField(max_length=15, validators=[validators.saudi_vat_number])
    cr_number = models.CharField(max_length=10, validators=[validators.commercial_registration])
    street = models.CharField(max_length=120)
    building_number = models.CharField(max_length=4, validators=[validators.building_number])
    district = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=5, validators=[validators.postal_code])
    country = models.CharField(max_length=2, default="SA")
    currency = models.CharField(max_length=3, default="SAR")
    prices_include_vat = models.BooleanField(default=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("25.00"))
    free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    b2b_enabled = models.BooleanField(default=False)
    upsell_config = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["handle"]

    def __str__(self):
        return self.handle

    def save(self, *args, **kwargs):
        from .resolver import forget_store

        super().save(*args, **kwargs)
        forget_store(self.handle)

    def seller_snapshot(self):
        return {
            "legal_name": self.legal_name,
            "vat_number": self.vat_number,
            "cr_number": self.cr_number,
            "street": self.street,
            "building_number": self.building_number,
            "district": self.district,
            "city": self.city,
            "postal_code": self.postal_code,
            "country": self.country,
        }


class TenantManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        if bypass_active():
            return queryset
        return queryset.filter(store_id=current_store_id())


class TenantModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="+", editable=False)

    objects = TenantManager()
    unscoped = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        active = current_store_id_or_none()
        if self.store_id is None:
            if active is None:
                raise TenantNotSet(f"Cannot save {type(self).__name__} without an active store.")
            self.store_id = active
        elif active is not None and self.store_id != active:
            raise CrossTenantWrite(f"{type(self).__name__} belongs to another store.")
        elif active is None and not bypass_active():
            raise TenantNotSet(f"Cannot save {type(self).__name__} without an active store.")
        super().save(*args, **kwargs)
