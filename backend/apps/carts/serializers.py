from rest_framework import serializers

from apps.common import validators
from apps.payments.models import StorePaymentMethod
from apps.tenancy.context import current_store

MONEY = {"max_digits": 12, "decimal_places": 2}


class AddressSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=16, validators=[validators.saudi_phone])
    email = serializers.EmailField(required=False, allow_blank=True)
    street = serializers.CharField(max_length=120)
    building_number = serializers.CharField(max_length=4, validators=[validators.building_number])
    additional_number = serializers.CharField(
        max_length=4, required=False, allow_blank=True, validators=[validators.building_number]
    )
    district = serializers.CharField(max_length=120)
    city = serializers.CharField(max_length=80)
    postal_code = serializers.CharField(max_length=5, validators=[validators.postal_code])
    country = serializers.ChoiceField(choices=["SA"], default="SA", help_text="Delivery is limited to Saudi Arabia.")


class BillingAddressSerializer(AddressSerializer):
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    vat_number = serializers.CharField(
        max_length=15, required=False, allow_blank=True, validators=[validators.saudi_vat_number]
    )
    cr_number = serializers.CharField(
        max_length=10, required=False, allow_blank=True, validators=[validators.commercial_registration]
    )

    def validate(self, attrs):
        if attrs.get("vat_number") and not attrs.get("company_name"):
            raise serializers.ValidationError({"company_name": "Required when a VAT number is given."})
        return attrs


class AddItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)


class UpdateItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)


class PaymentMethodChoiceSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=StorePaymentMethod.Method.choices)


class CheckoutSerializer(serializers.Serializer):
    payment_token = serializers.CharField(
        max_length=128, required=False, allow_null=True, help_text="Single-use token from the gateway's client SDK."
    )
    expected_total = serializers.DecimalField(
        required=False,
        allow_null=True,
        help_text="The total the shopper saw. Checkout fails with CART_TOTAL_CHANGED if it moved.",
        **MONEY,
    )
    po_number = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class ProductRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField()
    name_ar = serializers.CharField(allow_blank=True)
    kind = serializers.CharField()
    image_url = serializers.CharField(allow_blank=True)


class CartItemOutSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    product = ProductRefSerializer()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(**MONEY)
    subtotal = serializers.DecimalField(**MONEY)
    discount = serializers.DecimalField(**MONEY)
    net = serializers.DecimalField(**MONEY, help_text="Taxable amount after discount.")
    vat = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY, help_text="Amount including VAT.")
    available = serializers.BooleanField()


class CouponReasonSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    data = serializers.DictField(help_text="Values behind the reason, for example remaining or allowed_cities.")


class CartCouponSerializer(serializers.Serializer):
    code = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    applicable = serializers.BooleanField()
    reason = CouponReasonSerializer(allow_null=True)
    discount = serializers.DecimalField(**MONEY)


class PaymentMethodOutSerializer(serializers.Serializer):
    method = serializers.CharField()
    gateway = serializers.CharField()
    display_name = serializers.CharField()


class TotalsSerializer(serializers.Serializer):
    prices_include_vat = serializers.BooleanField()
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    subtotal = serializers.DecimalField(**MONEY, help_text="Items before discount, in the store's price basis.")
    discount = serializers.DecimalField(**MONEY)
    shipping = serializers.DecimalField(**MONEY, help_text="Shipping fee before any shipping discount.")
    taxable_amount = serializers.DecimalField(**MONEY)
    vat = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY, help_text="Amount payable, including VAT.")


class ReadinessSerializer(serializers.Serializer):
    ready = serializers.BooleanField()
    missing = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                "items",
                "shipping_address",
                "payment_method",
                "billing_address",
                "available_items",
                "applicable_coupon",
            ]
        )
    )


class WarningSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    item_id = serializers.UUIDField(required=False)
    available = serializers.IntegerField(required=False)
    previous_price = serializers.DecimalField(required=False, **MONEY)
    current_price = serializers.DecimalField(required=False, **MONEY)
    reason = serializers.CharField(required=False)


class CustomerRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    kind = serializers.CharField()


class CartSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    version = serializers.IntegerField(help_text="Send as If-Match to make a write conditional.")
    currency = serializers.CharField()
    customer = CustomerRefSerializer(allow_null=True)
    items = CartItemOutSerializer(many=True)
    coupon = CartCouponSerializer(allow_null=True)
    shipping_address = AddressSerializer(allow_null=True)
    billing_address = BillingAddressSerializer(allow_null=True)
    payment_method = PaymentMethodOutSerializer(allow_null=True)
    invoice_kind = serializers.ChoiceField(choices=["simplified", "standard"])
    totals = TotalsSerializer()
    checkout_readiness = ReadinessSerializer()
    warnings = WarningSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class CreatedCartSerializer(CartSerializer):
    cart_token = serializers.CharField(
        allow_null=True, help_text="Guest carts only. Send it back as X-Cart-Token. Shown once."
    )


def cart_payload(view):
    cart = view.cart
    priced = view.priced
    store_currency = current_store().currency
    unavailable_ids = {entry["item_id"] for entry in view.unavailable}
    coupon = None
    if view.coupon is not None:
        problem = view.coupon.problem
        coupon = {
            "code": view.coupon.coupon.code,
            "description": view.coupon.coupon.description,
            "applicable": view.coupon.applicable,
            "reason": {"code": str(problem.code), "detail": problem.detail or "", "data": problem.extra}
            if problem
            else None,
            "discount": priced.discount,
        }
    payment_method = None
    if view.payment_method is not None:
        payment_method = {
            "method": view.payment_method.method,
            "gateway": view.payment_method.gateway,
            "display_name": view.payment_method.display_name,
        }
    customer = cart.customer
    return {
        "id": cart.pk,
        "status": cart.status,
        "version": cart.version,
        "currency": store_currency,
        "customer": {"id": customer.pk, "name": customer.name, "kind": customer.kind} if customer else None,
        "items": [
            {
                "id": item.pk,
                "product": {
                    "id": item.product.pk,
                    "sku": item.product.sku,
                    "name": item.product.name,
                    "name_ar": item.product.name_ar,
                    "kind": item.product.kind,
                    "image_url": item.product.image_url,
                },
                "quantity": item.quantity,
                "unit_price": priced.line(str(item.pk)).unit_price,
                "subtotal": priced.line(str(item.pk)).subtotal,
                "discount": priced.line(str(item.pk)).discount,
                "net": priced.line(str(item.pk)).net,
                "vat": priced.line(str(item.pk)).vat,
                "total": priced.line(str(item.pk)).total,
                "available": str(item.pk) not in unavailable_ids,
            }
            for item in view.items
        ],
        "coupon": coupon,
        "shipping_address": cart.shipping_address,
        "billing_address": cart.billing_address,
        "payment_method": payment_method,
        "invoice_kind": view.invoice_kind,
        "totals": {
            "prices_include_vat": priced.prices_include_vat,
            "vat_rate": priced.vat_rate,
            "subtotal": priced.subtotal,
            "discount": priced.discount,
            "shipping": priced.shipping_fee,
            "taxable_amount": priced.taxable_amount,
            "vat": priced.vat,
            "total": priced.total,
        },
        "checkout_readiness": {"ready": view.ready, "missing": view.missing},
        "warnings": view.warnings,
        "created_at": cart.created_at,
        "updated_at": cart.updated_at,
    }
