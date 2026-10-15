import base64
import threading
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import responses
from django.conf import settings
from django.db import connection
from lxml import etree

from apps.carts.pricing import PricingLine, PricingPolicy, price_cart
from apps.invoicing import services
from apps.invoicing.models import EgsDevice, Invoice
from apps.invoicing.zatca import qr
from apps.invoicing.zatca.builder import CAC, CBC, InvoiceDocument, InvoiceLine, Party, PartyAddress, build_invoice_xml
from apps.invoicing.zatca.client import HttpZatcaClient, Outcome
from apps.invoicing.zatca.signing import FIRST_PREVIOUS_HASH, invoice_hash, sign_invoice, verify_signed_invoice
from apps.orders.models import Order, OrderLine
from apps.tenancy.context import tenant_context
from conftest import BILLING

NS = {"cac": CAC, "cbc": CBC}


def make_order(store, *, kind="simplified", lines=(("Oud Royale", 3, "99.99"),), method="card"):
    pricing_lines = [
        PricingLine(key=str(i), product_id=str(i), quantity=qty, unit_price=Decimal(price))
        for i, (_, qty, price) in enumerate(lines)
    ]
    policy = PricingPolicy(store.prices_include_vat, store.vat_rate, store.shipping_fee, store.free_shipping_threshold)
    priced = price_cart(pricing_lines, policy)
    buyer = {"kind": "individual", "name": "Noura"}
    if kind == "standard":
        buyer = {
            "kind": "business",
            "name": "Khalid",
            "company_name": BILLING["company_name"],
            "vat_number": BILLING["vat_number"],
            "cr_number": BILLING["cr_number"],
        }
    order = Order.objects.create(
        number=Order.next_number(),
        status=Order.Status.PAID,
        currency="SAR",
        prices_include_vat=priced.prices_include_vat,
        vat_rate=priced.vat_rate,
        subtotal=priced.subtotal,
        item_discount=priced.item_discount,
        shipping_fee=priced.shipping.subtotal,
        shipping_discount=priced.shipping_discount,
        shipping_net=priced.shipping.net,
        shipping_vat=priced.shipping.vat,
        taxable_amount=priced.taxable_amount,
        vat_total=priced.vat,
        total=priced.total,
        buyer=buyer,
        billing_address=BILLING if kind == "standard" else None,
        payment_method=method,
        payment_gateway="fakepay",
        invoice_kind=kind,
    )
    for position, ((name, qty, _), priced_line) in enumerate(zip(lines, priced.lines, strict=True), start=1):
        OrderLine.objects.create(
            order=order,
            position=position,
            sku=f"SKU-{position}",
            name=name,
            kind="physical",
            track_stock=True,
            quantity=qty,
            unit_price=priced_line.unit_price,
            subtotal=priced_line.subtotal,
            discount=priced_line.discount,
            net=priced_line.net,
            vat_rate=priced.vat_rate,
            vat=priced_line.vat,
            total=priced_line.total,
        )
    return order


def parsed(invoice):
    return etree.fromstring(invoice.signed_xml.encode())


def test_tlv_round_trip_and_size_guard():
    encoded = qr.encode_tlv([(1, "متجر العود"), (2, "399999999900003"), (8, b"\x01\x02")])
    assert qr.decode_tlv(encoded) == {1: "متجر العود".encode(), 2: b"399999999900003", 8: b"\x01\x02"}
    with pytest.raises(ValueError):
        qr.encode_tlv([(1, "x" * 256)])


@pytest.mark.parametrize(
    "quantity,net,expected",
    [
        (1, "86.95", [(1, "86.95")]),
        (3, "300.00", [(3, "100.00")]),
        (3, "260.86", [(2, "86.95"), (1, "86.96")]),
    ],
)
def test_lines_split_so_quantity_times_price_is_exact(quantity, net, expected):
    parts = services.split_by_quantity(quantity, Decimal(net), Decimal("13.04"))
    assert [(q, f"{Decimal(u):.2f}") for q, u, _, _ in parts] == expected
    assert sum(n for _, _, n, _ in parts) == Decimal(net)
    assert sum(v for _, _, _, v in parts) == Decimal("13.04")
    assert all(Decimal(u) * q == n for q, u, n, _ in parts)


def test_simplified_invoice_is_signed_chained_and_carries_a_qr(store):
    invoice, created = services.issue_invoice(make_order(store))
    root = parsed(invoice)
    assert created
    assert root.find("cbc:InvoiceTypeCode", NS).get("name") == "0200000"
    assert invoice.icv == 1 and invoice.pih == FIRST_PREVIOUS_HASH
    assert verify_signed_invoice(invoice.signed_xml) == (True, "")
    assert invoice_hash(invoice.signed_xml.encode()) == invoice.invoice_hash
    fields = qr.decode_tlv(invoice.qr_base64)
    assert sorted(fields) == list(range(1, 10))
    assert fields[2] == store.vat_number.encode()
    assert fields[4].decode() == f"{invoice.total:.2f}"
    assert fields[6].decode() == invoice.invoice_hash


def test_invoice_totals_reconcile_with_the_lines(store):
    invoice, _ = services.issue_invoice(make_order(store, lines=(("A", 3, "86.96"), ("B", 1, "0.01"))))
    root = parsed(invoice)
    lines = root.findall("cac:InvoiceLine", NS)
    line_net = sum(Decimal(line.find("cbc:LineExtensionAmount", NS).text) for line in lines)
    line_vat = sum(Decimal(line.find("cac:TaxTotal/cbc:TaxAmount", NS).text) for line in lines)
    for line in lines:
        quantity = Decimal(line.find("cbc:InvoicedQuantity", NS).text)
        price = Decimal(line.find("cac:Price/cbc:PriceAmount", NS).text)
        assert quantity * price == Decimal(line.find("cbc:LineExtensionAmount", NS).text)
    assert line_net == Decimal(root.find("cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount", NS).text)
    assert line_vat == Decimal(root.find("cac:TaxTotal/cbc:TaxAmount", NS).text)
    payable = Decimal(root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", NS).text)
    assert payable == line_net + line_vat == invoice.total


def test_standard_invoice_names_the_buyer_and_is_cleared(store, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        invoice, _ = services.issue_invoice(make_order(store, kind="standard", method="net_terms"))
    invoice.refresh_from_db()
    root = parsed(invoice)
    buyer = root.find("cac:AccountingCustomerParty/cac:Party", NS)
    assert root.find("cbc:InvoiceTypeCode", NS).get("name") == "0100000"
    assert buyer.find("cac:PartyTaxScheme/cbc:CompanyID", NS).text == BILLING["vat_number"]
    assert buyer.find("cac:PostalAddress/cbc:BuildingNumber", NS).text == BILLING["building_number"]
    assert root.find("cac:PaymentMeans/cbc:PaymentMeansCode", NS).text == "30"
    assert 9 not in qr.decode_tlv(invoice.qr_base64)
    assert (invoice.status, invoice.cleared_xml) == ("cleared", invoice.signed_xml)


def test_hash_chain_links_each_invoice_to_the_previous_one(store):
    invoices = [services.issue_invoice(make_order(store))[0] for _ in range(4)]
    assert [i.icv for i in invoices] == [1, 2, 3, 4]
    assert [i.pih for i in invoices[1:]] == [i.invoice_hash for i in invoices[:-1]]
    device = EgsDevice.objects.get()
    assert (device.last_icv, device.last_invoice_hash) == (4, invoices[-1].invoice_hash)


def test_issuing_twice_returns_the_same_invoice(store):
    order = make_order(store)
    first, created = services.issue_invoice(order)
    second, created_again = services.issue_invoice(order)
    assert (first.pk, created, created_again) == (second.pk, True, False)
    assert EgsDevice.objects.get().last_icv == 1


def test_signed_invoices_are_immutable(store):
    invoice, _ = services.issue_invoice(make_order(store))
    invoice.signed_xml = invoice.signed_xml.replace("Oud Royale", "Something else")
    with pytest.raises(ValueError):
        invoice.save()


def test_tampered_xml_fails_verification(store):
    invoice, _ = services.issue_invoice(make_order(store))
    tampered = invoice.signed_xml.replace(">Noura<", ">Mallory<")
    assert verify_signed_invoice(tampered)[0] is False


def test_credit_note_references_the_original_and_waits_for_it(store):
    order = make_order(store)
    original, _ = services.issue_invoice(order)
    credit, _ = services.issue_credit_note(order, "Customer returned the item")
    root = parsed(credit)
    assert root.find("cbc:InvoiceTypeCode", NS).text == "381"
    assert root.find("cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID", NS).text == original.number
    assert root.find("cac:PaymentMeans/cbc:InstructionNote", NS).text == "Customer returned the item"
    assert services.submit(credit) == "awaiting_original"
    assert services.submit(original) == "reported"
    credit.refresh_from_db()
    assert services.submit(credit) == "reported"


def golden_document():
    address = PartyAddress("King Fahd Road", "1234", "Al Olaya", "Riyadh", "12211")
    return InvoiceDocument(
        doc_type="invoice",
        kind="simplified",
        number="INV-100001",
        uuid="6f4d20e0-6bfe-4a80-9389-7dabe6620f12",
        icv=1,
        pih=FIRST_PREVIOUS_HASH,
        issued_at=datetime(2026, 10, 15, 12, 30, 0, tzinfo=ZoneInfo("Asia/Riyadh")),
        seller=Party("Oud and Amber Trading Company", "399999999900003", "1010010000", address),
        buyer=Party("Noura"),
        lines=(InvoiceLine("Oud Royale", 1, Decimal("100.00"), Decimal("100.00"), Decimal("15.00"), Decimal("15.00")),),
        taxable_amount=Decimal("100.00"),
        vat_total=Decimal("15.00"),
        payable=Decimal("115.00"),
        vat_rate=Decimal("15.00"),
        payment_method="card",
    )


def test_invoice_hash_is_stable_for_a_fixed_document():
    assert invoice_hash(build_invoice_xml(golden_document())) == "bAMP22SzabTkJCPInv6ynLbh2L3fK3FfMxsJkFBfPQk="


def test_signed_properties_digest_matches_the_embedded_block(store):
    device = EgsDevice.objects.get()
    signed = sign_invoice(
        build_invoice_xml(golden_document()),
        private_key_pem=device.private_key_pem,
        certificate_b64=device.certificate_b64,
        signing_time="2026-10-15T12:30:00",
        include_certificate_signature=True,
    )
    assert signed.invoice_hash == "bAMP22SzabTkJCPInv6ynLbh2L3fK3FfMxsJkFBfPQk="
    assert "<xades:SigningTime>2026-10-15T12:30:00</xades:SigningTime>" in signed.xml
    assert signed.xml.count("<cac:Signature>") == 1
    assert verify_signed_invoice(signed.xml) == (True, "")


def zatca_client(store):
    device = EgsDevice.objects.get()
    device.binary_security_token, device.api_secret = "dG9rZW4=", "secret"
    return HttpZatcaClient(device, settings.ZATCA_SIMULATION_URL)


REPORT_URL = f"{settings.ZATCA_SIMULATION_URL}/invoices/reporting/single"
CLEAR_URL = f"{settings.ZATCA_SIMULATION_URL}/invoices/clearance/single"


@pytest.mark.parametrize(
    "status,body,outcome",
    [
        (200, {"reportingStatus": "REPORTED", "validationResults": {}}, Outcome.ACCEPTED),
        (
            202,
            {"reportingStatus": "REPORTED", "validationResults": {"warningMessages": [{"code": "BR-KSA-08"}]}},
            Outcome.ACCEPTED,
        ),
        (200, {"reportingStatus": "NOT_REPORTED", "validationResults": {}}, Outcome.REJECTED),
        (
            400,
            {"reportingStatus": "NOT_REPORTED", "validationResults": {"errorMessages": [{"code": "BR-01"}]}},
            Outcome.REJECTED,
        ),
        (401, {}, Outcome.RETRY),
        (429, {}, Outcome.RETRY),
        (503, {}, Outcome.RETRY),
    ],
)
def test_reporting_responses_are_classified(store, status, body, outcome):
    with responses.RequestsMock() as mock:
        mock.post(REPORT_URL, json=body, status=status)
        result = zatca_client(store).report(invoice_hash="h", uuid="u", signed_xml="<Invoice/>")
    assert result.outcome == outcome


def test_gateway_html_page_is_retried(store):
    with responses.RequestsMock() as mock:
        mock.post(REPORT_URL, body="<html>Bad gateway</html>", status=200, content_type="text/html")
        assert zatca_client(store).report(invoice_hash="h", uuid="u", signed_xml="<Invoice/>").outcome == Outcome.RETRY


def test_clearance_stores_the_stamped_xml(store):
    stamped = "<Invoice>stamped</Invoice>"
    with responses.RequestsMock() as mock:
        mock.post(
            CLEAR_URL,
            json={"clearanceStatus": "CLEARED", "clearedInvoice": base64.b64encode(stamped.encode()).decode()},
        )
        result = zatca_client(store).clear(invoice_hash="h", uuid="u", signed_xml="<Invoice/>")
    assert (result.outcome, result.cleared_xml) == (Outcome.ACCEPTED, stamped)


def test_transient_failure_keeps_the_invoice_pending(store, monkeypatch):
    invoice, _ = services.issue_invoice(make_order(store))
    EgsDevice.objects.update(environment=EgsDevice.Environment.SIMULATION)
    invoice.refresh_from_db()
    with responses.RequestsMock() as mock:
        mock.post(REPORT_URL, status=502, body="upstream down")
        assert services.submit(invoice) == "pending_retry"
    invoice.refresh_from_db()
    assert (invoice.status, invoice.submission_attempts) == ("pending_retry", 1)


@pytest.mark.django_db(transaction=True)
def test_concurrent_issuing_keeps_the_chain_gapless():
    from conftest import build_store

    store = build_store()
    with tenant_context(store):
        orders = [make_order(store) for _ in range(8)]
    barrier = threading.Barrier(len(orders) * 2)
    errors = []

    def issue(order):
        try:
            barrier.wait(timeout=10)
            with tenant_context(store):
                services.issue_invoice(order)
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=issue, args=(order,)) for order in orders * 2]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors
    with tenant_context(store):
        invoices = list(Invoice.objects.order_by("icv"))
        assert [i.icv for i in invoices] == list(range(1, 9))
        assert len({i.order_id for i in invoices}) == 8
        assert [i.pih for i in invoices[1:]] == [i.invoice_hash for i in invoices[:-1]]
        assert all(verify_signed_invoice(i.signed_xml)[0] for i in invoices)


def test_sweepers_issue_missing_invoices_then_submit_them(store):
    from datetime import timedelta

    from django.utils import timezone

    from apps.invoicing import tasks

    order = make_order(store)
    Order.objects.filter(pk=order.pk).update(updated_at=timezone.now() - timedelta(minutes=10))
    assert tasks.sweep_uninvoiced_orders() == 1
    assert tasks.sweep_uninvoiced_orders() == 0
    Invoice.objects.update(issued_at=timezone.now() - timedelta(minutes=10))
    assert tasks.submit_due_invoices() == {"reported": 1}
    assert Invoice.objects.get().status == "reported"


def test_invoice_endpoint_reads_lines_back_from_the_signed_xml(store, django_capture_on_commit_callbacks):
    from apps.invoicing.serializers import InvoiceSerializer, invoice_payload

    with django_capture_on_commit_callbacks(execute=True):
        invoice, _ = services.issue_invoice(make_order(store, kind="standard", lines=(("Chair", 3, "86.96"),)))
    payload = InvoiceSerializer(invoice_payload(invoice)).data
    assert [(line["quantity"], line["unit_price"]) for line in payload["lines"][:2]] == [(2, "75.61"), (1, "75.63")]
    assert sum(Decimal(line["net"]) for line in payload["lines"]) == invoice.taxable_amount
    assert sum(Decimal(line["total"]) for line in payload["lines"]) == invoice.total
    assert payload["buyer"]["vat_number"] == BILLING["vat_number"]
    assert payload["buyer"]["address"]["building_number"] == BILLING["building_number"]
    assert payload["seller"]["vat_number"] == store.vat_number
    assert payload["order_number"].startswith("ORD-")


def test_invoice_lines_carry_the_arabic_name(store):
    order = make_order(store)
    OrderLine.objects.filter(order=order).update(name_ar="عود رويال")
    invoice, _ = services.issue_invoice(order)
    names = [line.find("cac:Item/cbc:Name", NS).text for line in parsed(invoice).findall("cac:InvoiceLine", NS)]
    assert names[0] == "Oud Royale | عود رويال"
    assert names[-1] == "Shipping | الشحن"
    assert verify_signed_invoice(invoice.signed_xml) == (True, "")
