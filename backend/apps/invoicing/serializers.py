from rest_framework import serializers

from apps.carts.serializers import MONEY

from .zatca.reader import read_invoice


class InvoiceSellerSerializer(serializers.Serializer):
    legal_name = serializers.CharField()
    vat_number = serializers.CharField()
    cr_number = serializers.CharField()
    street = serializers.CharField()
    building_number = serializers.CharField()
    district = serializers.CharField()
    city = serializers.CharField()
    postal_code = serializers.CharField()
    country = serializers.CharField()


class InvoiceAddressSerializer(serializers.Serializer):
    street = serializers.CharField()
    building_number = serializers.CharField()
    district = serializers.CharField()
    city = serializers.CharField()
    postal_code = serializers.CharField()
    country = serializers.CharField()


class InvoiceBuyerSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True)
    vat_number = serializers.CharField(allow_blank=True)
    cr_number = serializers.CharField(allow_blank=True)
    address = InvoiceAddressSerializer(allow_null=True)


class InvoiceLineSerializer(serializers.Serializer):
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(**MONEY, help_text="Net unit price, excluding VAT.")
    net = serializers.DecimalField(**MONEY)
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    vat = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)


class InvoiceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    doc_type = serializers.CharField()
    kind = serializers.ChoiceField(choices=["simplified", "standard"])
    status = serializers.CharField(help_text="issued, pending_retry, reported, cleared or rejected.")
    uuid = serializers.UUIDField()
    icv = serializers.IntegerField(help_text="Invoice counter value in the device's hash chain.")
    invoice_hash = serializers.CharField()
    previous_invoice_hash = serializers.CharField()
    issued_at = serializers.DateTimeField()
    order_number = serializers.CharField()
    po_number = serializers.CharField(allow_blank=True)
    billing_reference = serializers.CharField(allow_blank=True, help_text="Original invoice, for credit notes.")
    qr_code = serializers.CharField(help_text="Base64 TLV payload to render as a QR code.")
    seller = InvoiceSellerSerializer()
    buyer = InvoiceBuyerSerializer()
    lines = InvoiceLineSerializer(many=True, help_text="Read back from the signed XML, exactly as submitted.")
    taxable_amount = serializers.DecimalField(**MONEY)
    vat_total = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)
    zatca_warnings = serializers.ListField(child=serializers.DictField())
    xml_url = serializers.CharField()


def invoice_payload(invoice):
    document = read_invoice(invoice.signed_xml)
    return {
        "id": invoice.pk,
        "number": invoice.number,
        "doc_type": invoice.doc_type,
        "kind": invoice.kind,
        "status": invoice.status,
        "uuid": invoice.uuid,
        "icv": invoice.icv,
        "invoice_hash": invoice.invoice_hash,
        "previous_invoice_hash": invoice.pih,
        "issued_at": invoice.issued_at,
        "order_number": invoice.order.display_number,
        "po_number": document["po_number"],
        "billing_reference": document["billing_reference"],
        "qr_code": invoice.qr_base64,
        "seller": invoice.seller,
        "buyer": document["buyer"],
        "lines": document["lines"],
        "taxable_amount": invoice.taxable_amount,
        "vat_total": invoice.vat_total,
        "total": invoice.total,
        "zatca_warnings": invoice.zatca_warnings,
        "xml_url": f"/api/v1/orders/{invoice.order_id}/invoice?format=xml",
    }
