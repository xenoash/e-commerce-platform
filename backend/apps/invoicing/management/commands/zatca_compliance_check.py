import base64
import json
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.invoicing.zatca.builder import InvoiceDocument, InvoiceLine, Party, PartyAddress, build_invoice_xml
from apps.invoicing.zatca.crypto import build_csr, csr_b64, generate_private_key, private_key_pem
from apps.invoicing.zatca.signing import FIRST_PREVIOUS_HASH, sign_invoice
from apps.tenancy.models import Store

DEVELOPER_PORTAL_OTP = "123345"
HEADERS = {"Accept": "application/json", "Accept-Version": "V2", "Accept-Language": "en"}


def line(name, quantity, unit_price, net, vat):
    return InvoiceLine(name, quantity, Decimal(unit_price), Decimal(net), Decimal(vat), Decimal("15.00"))


class Command(BaseCommand):
    help = (
        "Onboard a throwaway EGS against ZATCA's developer portal (public sandbox, dummy data) and run its "
        "compliance validation on a simplified and a standard invoice built by this codebase."
    )

    def add_arguments(self, parser):
        parser.add_argument("--store", default="oud-and-amber")
        parser.add_argument("--otp", default=DEVELOPER_PORTAL_OTP)

    def handle(self, *args, store, otp, **options):
        self.verbosity = options.get("verbosity", 1)
        store = Store.objects.filter(handle=store).first()
        if store is None:
            raise CommandError("Unknown store. Run seed_demo first.")
        base = settings.ZATCA_DEVELOPER_PORTAL_URL
        key = generate_private_key()
        serial = f"1-EcommercePlatform|2-1.0|3-{uuid.uuid4()}"
        csr = build_csr(
            key,
            common_name=f"EGS-{store.handle}",
            organization=store.legal_name,
            organization_unit=store.city,
            vat_number=store.vat_number,
            serial_number=serial,
            environment="developer_portal",
            address=f"{store.building_number} {store.street}, {store.city}",
            business_category="Retail",
        )
        response = requests.post(
            f"{base}/compliance",
            headers={**HEADERS, "OTP": otp, "Content-Type": "application/json"},
            json={"csr": csr_b64(csr)},
            timeout=30,
        )
        if response.status_code != 200:
            raise CommandError(f"Compliance CSID request failed: {response.status_code} {response.text[:500]}")
        csid = response.json()
        token = csid["binarySecurityToken"]
        certificate = base64.b64decode(token).decode()
        self.stdout.write(self.style.SUCCESS(f"Compliance CSID issued (request {csid.get('requestID')})"))

        previous_hash = FIRST_PREVIOUS_HASH
        for icv, kind in enumerate(("simplified", "standard"), start=1):
            document = self._document(store, kind, icv, previous_hash)
            signed = sign_invoice(
                build_invoice_xml(document),
                private_key_pem=private_key_pem(key),
                certificate_b64=certificate,
                signing_time=document.issued_at.strftime("%Y-%m-%dT%H:%M:%S"),
                include_certificate_signature=kind == "simplified",
            )
            result = requests.post(
                f"{base}/compliance/invoices",
                headers={**HEADERS, "Content-Type": "application/json"},
                auth=(token, csid["secret"]),
                json={
                    "invoiceHash": signed.invoice_hash,
                    "uuid": document.uuid,
                    "invoice": base64.b64encode(signed.xml.encode()).decode(),
                },
                timeout=30,
            )
            self._report(kind, result)
            previous_hash = signed.invoice_hash

    def _document(self, store, kind, icv, previous_hash):
        seller_address = PartyAddress(
            store.street, store.building_number, store.district, store.city, store.postal_code
        )
        buyer = Party("Noura Al-Qahtani")
        if kind == "standard":
            buyer = Party(
                "Acme Arabia Trading Co.",
                vat_number="310175397400003",
                cr_number="1010123456",
                address=PartyAddress("Olaya Street", "7788", "Al Wurud", "Riyadh", "12251"),
            )
        return InvoiceDocument(
            doc_type="invoice",
            kind=kind,
            number=f"INV-CHECK-{icv}",
            uuid=str(uuid.uuid4()),
            icv=icv,
            pih=previous_hash,
            issued_at=datetime.now(ZoneInfo("Asia/Riyadh")).replace(microsecond=0),
            seller=Party(store.legal_name, store.vat_number, store.cr_number, seller_address),
            buyer=buyer,
            lines=(
                line("Oud Royale 50ml", 2, "86.95", "173.90", "26.08"),
                line("Oud Royale 50ml", 1, "86.96", "86.96", "13.05"),
                line("Shipping", 1, "21.74", "21.74", "3.26"),
            ),
            taxable_amount=Decimal("282.60"),
            vat_total=Decimal("42.39"),
            payable=Decimal("324.99"),
            vat_rate=Decimal("15.00"),
            payment_method="card",
            po_number="PO-CHECK-1" if kind == "standard" else "",
        )

    def _report(self, kind, response):
        try:
            payload = response.json()
        except ValueError:
            self.stdout.write(self.style.ERROR(f"{kind}: HTTP {response.status_code} {response.text[:300]}"))
            return
        results = payload.get("validationResults") or {}
        status = results.get("status") or payload.get("reportingStatus") or payload.get("clearanceStatus")
        style = self.style.SUCCESS if status in ("PASS", "WARNING") else self.style.ERROR
        self.stdout.write(style(f"{kind}: HTTP {response.status_code} validation={status}"))
        for bucket in ("warningMessages", "errorMessages"):
            for message in results.get(bucket) or []:
                self.stdout.write(f"  {bucket[:-8]} {message.get('code')}: {message.get('message')}")
        if self.verbosity > 1:
            self.stdout.write(json.dumps(payload, indent=2))
