from django.db import connection, models
from django.db.models import Q

from apps.tenancy.models import TenantModel


class Order(TenantModel):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment"
        PAID = "paid"
        CONFIRMED = "confirmed"
        PAYMENT_FAILED = "payment_failed"
        EXPIRED = "expired"
        CANCELLED = "cancelled"
        NEEDS_ATTENTION = "needs_attention"

    class InvoiceKind(models.TextChoices):
        SIMPLIFIED = "simplified"
        STANDARD = "standard"

    FULFILLABLE_STATUSES = (Status.PAID, Status.CONFIRMED)
    CLOSED_UNPAID_STATUSES = (Status.PAYMENT_FAILED, Status.EXPIRED, Status.CANCELLED)

    number = models.BigIntegerField(unique=True)
    cart = models.ForeignKey("carts.Cart", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    customer = models.ForeignKey(
        "customers.Customer", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    token_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    currency = models.CharField(max_length=3)
    prices_include_vat = models.BooleanField()
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    item_discount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_discount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_net = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_vat = models.DecimalField(max_digits=12, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    vat_total = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    coupon = models.ForeignKey("promotions.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    coupon_code = models.CharField(max_length=40, blank=True)
    buyer = models.JSONField()
    shipping_address = models.JSONField(null=True, blank=True)
    billing_address = models.JSONField(null=True, blank=True)
    po_number = models.CharField(max_length=64, blank=True)
    payment_method = models.CharField(max_length=32)
    payment_gateway = models.CharField(max_length=32)
    invoice_kind = models.CharField(max_length=16, choices=InvoiceKind.choices)
    expires_at = models.DateTimeField(null=True, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-placed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart"], condition=Q(status="pending_payment"), name="one_pending_order_per_cart"
            ),
            models.CheckConstraint(condition=Q(total__gte=0), name="order_total_not_negative"),
        ]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="order_status_expiry"),
            models.Index(fields=["store", "customer", "-placed_at"], name="order_customer_recent"),
        ]

    @property
    def display_number(self):
        return f"ORD-{self.number}"

    @property
    def discount_total(self):
        return self.item_discount + self.shipping_discount

    def store_payment_method(self, gateway=None):
        from apps.payments.models import StorePaymentMethod

        gateway = gateway or self.payment_gateway
        configured = StorePaymentMethod.objects.filter(method=self.payment_method, gateway=gateway).first()
        return configured or StorePaymentMethod(method=self.payment_method, gateway=gateway, config={})

    @staticmethod
    def next_number():
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval('order_number_seq')")
            return cursor.fetchone()[0]


class OrderLine(TenantModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    position = models.PositiveSmallIntegerField()
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=16)
    track_stock = models.BooleanField()
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2)
    net = models.DecimalField(max_digits=12, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    vat = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["position"]
