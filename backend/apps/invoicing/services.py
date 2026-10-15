import logging
import uuid
from decimal import ROUND_DOWN
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.common.errors import ErrorCode, Problem
from apps.common.money import CENT, allocate
from apps.orders.models import Order
from apps.tenancy.context import current_store, current_store_id

from .models import EgsDevice, Invoice
from .zatca.builder import InvoiceDocument, InvoiceLine, Party, PartyAddress, build_invoice_xml
from .zatca.client import Outcome, client_for
from .zatca.signing import sign_invoice

logger = logging.getLogger(__name__)

RIYADH = ZoneInfo("Asia/Riyadh")


class NoActiveDevice(RuntimeError):
    pass


def split_by_quantity(quantity, net, vat):
    unit = (net / quantity).quantize(CENT, rounding=ROUND_DOWN)
    if quantity == 1 or unit * quantity == net:
        return [(quantity, net / quantity if quantity > 1 else net, net, vat)]
    bulk_net = unit * (quantity - 1)
    rest_net = net - bulk_net
    bulk_vat, rest_vat = allocate(vat, [bulk_net, rest_net])
    return [(quantity - 1, unit, bulk_net, bulk_vat), (1, rest_net, rest_net, rest_vat)]


def bilingual(name, name_ar):
    return f"{name} | {name_ar}" if name_ar else name


def invoice_lines(order):
    lines = []
    for line in order.lines.all():
        name = bilingual(line.name, line.name_ar)
        for quantity, unit_price, net, vat in split_by_quantity(line.quantity, line.net, line.vat):
            lines.append(
                InvoiceLine(
                    name=name, quantity=quantity, unit_price=unit_price, net=net, vat=vat, vat_rate=line.vat_rate
                )
            )
    if order.shipping_net or order.shipping_vat:
        lines.append(
            InvoiceLine(
                name=bilingual("Shipping", "الشحن"),
                quantity=1,
                unit_price=order.shipping_net,
                net=order.shipping_net,
                vat=order.shipping_vat,
                vat_rate=order.vat_rate,
            )
        )
    return tuple(lines)


def _address(data):
    if not data:
        return None
    return PartyAddress(
        street=data["street"],
        building_number=data["building_number"],
        district=data["district"],
        city=data["city"],
        postal_code=data["postal_code"],
        country=data.get("country", "SA"),
    )


def seller_party(snapshot):
    return Party(
        name=snapshot["legal_name"],
        vat_number=snapshot["vat_number"],
        cr_number=snapshot["cr_number"],
        address=_address(snapshot),
    )


def buyer_party(order):
    buyer = order.buyer
    if order.invoice_kind == Order.InvoiceKind.STANDARD:
        return Party(
            name=buyer.get("company_name") or buyer.get("name", ""),
            vat_number=buyer.get("vat_number", ""),
            cr_number=buyer.get("cr_number", ""),
            address=_address(order.billing_address),
        )
    return Party(name=buyer.get("name", ""))


def _issue(order, *, doc_type, kind, number, reason="", billing_reference=None):
    with transaction.atomic():
        device = EgsDevice.objects.select_for_update().filter(is_active=True).first()
        if device is None:
            raise NoActiveDevice(f"Store {current_store().handle} has no active e-invoicing device.")
        existing = Invoice.objects.filter(order=order, doc_type=doc_type).first()
        if existing is not None:
            return existing, False
        store = current_store()
        issued_at = timezone.now().astimezone(RIYADH).replace(microsecond=0)
        seller_snapshot = store.seller_snapshot()
        document = InvoiceDocument(
            doc_type=doc_type,
            kind=kind,
            number=number,
            uuid=str(uuid.uuid4()),
            icv=device.last_icv + 1,
            pih=device.last_invoice_hash,
            issued_at=issued_at,
            seller=seller_party(seller_snapshot),
            buyer=buyer_party(order),
            lines=invoice_lines(order),
            taxable_amount=order.taxable_amount,
            vat_total=order.vat_total,
            payable=order.total,
            vat_rate=order.vat_rate,
            payment_method=order.payment_method,
            currency=order.currency,
            po_number=order.po_number,
            billing_reference=billing_reference.number if billing_reference else "",
            reason=reason,
        )
        signed = sign_invoice(
            build_invoice_xml(document),
            private_key_pem=device.private_key_pem,
            certificate_b64=device.certificate_b64,
            signing_time=issued_at.strftime("%Y-%m-%dT%H:%M:%S"),
            include_certificate_signature=kind == Invoice.Kind.SIMPLIFIED,
        )
        invoice = Invoice.objects.create(
            order=order,
            device=device,
            doc_type=doc_type,
            kind=kind,
            number=number,
            uuid=document.uuid,
            icv=document.icv,
            pih=document.pih,
            invoice_hash=signed.invoice_hash,
            issued_at=issued_at,
            signed_xml=signed.xml,
            qr_base64=signed.qr,
            seller=seller_snapshot,
            buyer=order.buyer,
            reason=reason,
            billing_reference=billing_reference,
            taxable_amount=order.taxable_amount,
            vat_total=order.vat_total,
            total=order.total,
        )
        device.last_icv = document.icv
        device.last_invoice_hash = signed.invoice_hash
        device.save(update_fields=["last_icv", "last_invoice_hash"])
        schedule_submission(invoice)
        return invoice, True


def schedule_submission(invoice):
    from .tasks import submit_invoice

    store_id = str(current_store_id())
    invoice_id = str(invoice.pk)
    transaction.on_commit(lambda: submit_invoice.delay(invoice_id, store_id=store_id), robust=True)


def issue_invoice(order):
    if order.status not in Order.FULFILLABLE_STATUSES:
        return None, False
    return _issue(order, doc_type=Invoice.DocType.INVOICE, kind=order.invoice_kind, number=f"INV-{order.number}")


def issue_credit_note(order, reason):
    original = Invoice.objects.filter(order=order, doc_type=Invoice.DocType.INVOICE).first()
    if original is None:
        raise Problem(409, ErrorCode.INVOICE_NOT_READY, "The order has no invoice to credit.")
    return _issue(
        order,
        doc_type=Invoice.DocType.CREDIT_NOTE,
        kind=original.kind,
        number=f"CRN-{order.number}",
        reason=reason,
        billing_reference=original,
    )


def submit(invoice):
    if invoice.status not in Invoice.SUBMITTABLE_STATUSES:
        return invoice.status
    if invoice.billing_reference_id and invoice.billing_reference.status not in Invoice.ACCEPTED_STATUSES:
        return "awaiting_original"
    client = client_for(invoice.device)
    submit_call = client.clear if invoice.kind == Invoice.Kind.STANDARD else client.report
    result = submit_call(invoice_hash=invoice.invoice_hash, uuid=str(invoice.uuid), signed_xml=invoice.signed_xml)
    accepted_status = Invoice.Status.CLEARED if invoice.kind == Invoice.Kind.STANDARD else Invoice.Status.REPORTED
    new_status = {
        Outcome.ACCEPTED: accepted_status,
        Outcome.REJECTED: Invoice.Status.REJECTED,
        Outcome.RETRY: Invoice.Status.PENDING_RETRY,
    }[result.outcome]
    fields = {
        "status": new_status,
        "zatca_status": result.status_label,
        "zatca_warnings": result.warnings,
        "zatca_errors": result.errors,
        "submitted_at": timezone.now(),
    }
    if result.cleared_xml:
        fields["cleared_xml"] = result.cleared_xml
    Invoice.objects.filter(pk=invoice.pk, status__in=Invoice.SUBMITTABLE_STATUSES).update(
        submission_attempts=invoice.submission_attempts + 1, **fields
    )
    if result.outcome == Outcome.REJECTED:
        logger.error("zatca_rejected invoice=%s errors=%s", invoice.number, result.errors)
    return new_status


def buyer_visible_invoice(order):
    invoice = Invoice.objects.filter(order=order, doc_type=Invoice.DocType.INVOICE).first()
    if invoice is None:
        raise Problem(409, ErrorCode.INVOICE_NOT_READY, "The invoice is being issued. Try again in a moment.")
    if invoice.kind == Invoice.Kind.STANDARD and invoice.status != Invoice.Status.CLEARED:
        raise Problem(
            409,
            ErrorCode.INVOICE_NOT_READY,
            "This tax invoice is awaiting ZATCA clearance and can be shared once cleared.",
            invoice_status=invoice.status,
        )
    return invoice
