from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models.functions import Lower

from apps.common import validators
from apps.tenancy.models import TenantModel


class Customer(TenantModel):
    class Kind(models.TextChoices):
        INDIVIDUAL = "individual"
        BUSINESS = "business"

    email = models.EmailField()
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=16, blank=True, validators=[validators.saudi_phone])
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.INDIVIDUAL)
    password = models.CharField(max_length=128)
    company_name = models.CharField(max_length=200, blank=True)
    vat_number = models.CharField(max_length=15, blank=True, validators=[validators.saudi_vat_number])
    cr_number = models.CharField(max_length=10, blank=True, validators=[validators.commercial_registration])
    credit_approved = models.BooleanField(default=False)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    is_authenticated = True
    is_anonymous = False

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), "store", name="customer_email_unique_per_store"),
        ]

    def __str__(self):
        return self.email

    @property
    def is_business(self):
        return self.kind == self.Kind.BUSINESS

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class AccessToken(TenantModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="tokens")
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
