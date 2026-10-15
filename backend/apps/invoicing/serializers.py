from rest_framework import serializers

from apps.carts.serializers import MONEY


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
    qr_code = serializers.CharField(help_text="Base64 TLV payload to render as a QR code.")
    seller = serializers.DictField()
    buyer = serializers.DictField()
    taxable_amount = serializers.DecimalField(**MONEY)
    vat_total = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)
    zatca_warnings = serializers.ListField(child=serializers.DictField())
    xml_url = serializers.CharField()


def invoice_payload(invoice):
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
        "qr_code": invoice.qr_base64,
        "seller": invoice.seller,
        "buyer": invoice.buyer,
        "taxable_amount": invoice.taxable_amount,
        "vat_total": invoice.vat_total,
        "total": invoice.total,
        "zatca_warnings": invoice.zatca_warnings,
        "xml_url": f"/api/v1/orders/{invoice.order_id}/invoice?format=xml",
    }
