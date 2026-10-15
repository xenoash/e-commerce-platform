from rest_framework import serializers

from apps.carts.serializers import MONEY, AddressSerializer, BillingAddressSerializer


class OrderLineSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    product_id = serializers.UUIDField(allow_null=True)
    sku = serializers.CharField()
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(**MONEY)
    subtotal = serializers.DecimalField(**MONEY)
    discount = serializers.DecimalField(**MONEY)
    net = serializers.DecimalField(**MONEY)
    vat = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)


class OrderTotalsSerializer(serializers.Serializer):
    prices_include_vat = serializers.BooleanField()
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    subtotal = serializers.DecimalField(**MONEY)
    discount = serializers.DecimalField(**MONEY)
    shipping = serializers.DecimalField(**MONEY)
    taxable_amount = serializers.DecimalField(**MONEY)
    vat = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)


class NextActionSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["redirect"])
    url = serializers.URLField()


class OrderPaymentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    method = serializers.CharField()
    gateway = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)
    next_action = NextActionSerializer(allow_null=True)
    failure_code = serializers.CharField(allow_blank=True)
    failure_message = serializers.CharField(allow_blank=True)


class InvoiceSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    kind = serializers.CharField()
    status = serializers.CharField()
    issued_at = serializers.DateTimeField()


class BuyerSerializer(serializers.Serializer):
    kind = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    company_name = serializers.CharField(allow_blank=True)
    vat_number = serializers.CharField(allow_blank=True)


class OrderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    status = serializers.CharField()
    currency = serializers.CharField()
    lines = OrderLineSerializer(many=True)
    totals = OrderTotalsSerializer()
    coupon_code = serializers.CharField(allow_blank=True)
    buyer = BuyerSerializer()
    shipping_address = AddressSerializer(allow_null=True)
    billing_address = BillingAddressSerializer(allow_null=True)
    po_number = serializers.CharField(allow_blank=True)
    invoice_kind = serializers.CharField()
    payment = OrderPaymentSerializer(allow_null=True)
    invoice = InvoiceSummarySerializer(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)
    placed_at = serializers.DateTimeField()
    paid_at = serializers.DateTimeField(allow_null=True)


def order_payload(order):
    from apps.invoicing.models import Invoice

    payment = order.payments.order_by("-created_at").first()
    invoice = Invoice.objects.filter(order=order, doc_type=Invoice.DocType.INVOICE).first()
    return {
        "id": order.pk,
        "number": order.display_number,
        "status": order.status,
        "currency": order.currency,
        "lines": [
            {
                "id": line.pk,
                "product_id": line.product_id,
                "sku": line.sku,
                "name": line.name,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "subtotal": line.subtotal,
                "discount": line.discount,
                "net": line.net,
                "vat": line.vat,
                "total": line.total,
            }
            for line in order.lines.all()
        ],
        "totals": {
            "prices_include_vat": order.prices_include_vat,
            "vat_rate": order.vat_rate,
            "subtotal": order.subtotal,
            "discount": order.discount_total,
            "shipping": order.shipping_fee,
            "taxable_amount": order.taxable_amount,
            "vat": order.vat_total,
            "total": order.total,
        },
        "coupon_code": order.coupon_code,
        "buyer": order.buyer,
        "shipping_address": order.shipping_address,
        "billing_address": order.billing_address,
        "po_number": order.po_number,
        "invoice_kind": order.invoice_kind,
        "payment": {
            "id": payment.pk,
            "method": payment.method,
            "gateway": payment.gateway,
            "status": payment.status,
            "amount": payment.amount,
            "next_action": payment.next_action,
            "failure_code": payment.failure_code,
            "failure_message": payment.failure_message,
        }
        if payment
        else None,
        "invoice": {
            "id": invoice.pk,
            "number": invoice.number,
            "kind": invoice.kind,
            "status": invoice.status,
            "issued_at": invoice.issued_at,
        }
        if invoice
        else None,
        "expires_at": order.expires_at if order.status == order.Status.PENDING_PAYMENT else None,
        "placed_at": order.placed_at,
        "paid_at": order.paid_at,
    }
