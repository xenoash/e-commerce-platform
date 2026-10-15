from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from lxml import etree

INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NSMAP = {None: INVOICE_NS, "cac": CAC, "cbc": CBC, "ext": EXT}

TYPE_CODES = {"invoice": "388", "credit_note": "381"}
SUBTYPES = {"simplified": "0200000", "standard": "0100000"}
PAYMENT_MEANS = {"card": "48", "apple_pay": "48", "cod": "10", "net_terms": "30"}


@dataclass(frozen=True)
class PartyAddress:
    street: str
    building_number: str
    district: str
    city: str
    postal_code: str
    country: str = "SA"


@dataclass(frozen=True)
class Party:
    name: str
    vat_number: str = ""
    cr_number: str = ""
    address: PartyAddress | None = None


@dataclass(frozen=True)
class InvoiceLine:
    name: str
    quantity: int
    unit_price: Decimal
    net: Decimal
    vat: Decimal
    vat_rate: Decimal


@dataclass(frozen=True)
class InvoiceDocument:
    doc_type: str
    kind: str
    number: str
    uuid: str
    icv: int
    pih: str
    issued_at: datetime
    seller: Party
    buyer: Party
    lines: tuple[InvoiceLine, ...]
    taxable_amount: Decimal
    vat_total: Decimal
    payable: Decimal
    vat_rate: Decimal
    payment_method: str
    currency: str = "SAR"
    po_number: str = ""
    billing_reference: str = ""
    reason: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


def _el(parent, ns, tag, text=None, **attributes):
    element = etree.SubElement(parent, f"{{{ns}}}{tag}", **attributes)
    if text is not None:
        element.text = str(text)
    return element


def _amount(parent, tag, value, currency):
    return _el(parent, CBC, tag, f"{Decimal(value):.2f}", currencyID=currency)


def _address(parent, address):
    postal = _el(parent, CAC, "PostalAddress")
    _el(postal, CBC, "StreetName", address.street)
    _el(postal, CBC, "BuildingNumber", address.building_number)
    _el(postal, CBC, "CitySubdivisionName", address.district)
    _el(postal, CBC, "CityName", address.city)
    _el(postal, CBC, "PostalZone", address.postal_code)
    country = _el(postal, CAC, "Country")
    _el(country, CBC, "IdentificationCode", address.country)


def _tax_scheme(parent):
    scheme = _el(parent, CAC, "TaxScheme")
    _el(scheme, CBC, "ID", "VAT")


def _seller(root, seller):
    party = _el(_el(root, CAC, "AccountingSupplierParty"), CAC, "Party")
    identification = _el(party, CAC, "PartyIdentification")
    _el(identification, CBC, "ID", seller.cr_number, schemeID="CRN")
    _address(party, seller.address)
    tax = _el(party, CAC, "PartyTaxScheme")
    _el(tax, CBC, "CompanyID", seller.vat_number)
    _tax_scheme(tax)
    _el(_el(party, CAC, "PartyLegalEntity"), CBC, "RegistrationName", seller.name)


def _buyer(root, buyer, kind):
    party = _el(_el(root, CAC, "AccountingCustomerParty"), CAC, "Party")
    if buyer.cr_number:
        identification = _el(party, CAC, "PartyIdentification")
        _el(identification, CBC, "ID", buyer.cr_number, schemeID="CRN")
    if buyer.address is not None:
        _address(party, buyer.address)
    if buyer.vat_number:
        tax = _el(party, CAC, "PartyTaxScheme")
        _el(tax, CBC, "CompanyID", buyer.vat_number)
        _tax_scheme(tax)
    elif kind == "standard":
        raise ValueError("A standard tax invoice needs the buyer's VAT number.")
    if buyer.name:
        _el(_el(party, CAC, "PartyLegalEntity"), CBC, "RegistrationName", buyer.name)


def _tax_category(parent, tag, rate):
    category = _el(parent, CAC, tag)
    _el(category, CBC, "ID", "S")
    _el(category, CBC, "Percent", f"{Decimal(rate):.2f}")
    _tax_scheme(category)


def build_invoice_xml(document: InvoiceDocument) -> bytes:
    currency = document.currency
    root = etree.Element(f"{{{INVOICE_NS}}}Invoice", nsmap=NSMAP)
    _el(root, CBC, "ProfileID", "reporting:1.0")
    _el(root, CBC, "ID", document.number)
    _el(root, CBC, "UUID", document.uuid)
    _el(root, CBC, "IssueDate", document.issued_at.strftime("%Y-%m-%d"))
    _el(root, CBC, "IssueTime", document.issued_at.strftime("%H:%M:%S"))
    _el(root, CBC, "InvoiceTypeCode", TYPE_CODES[document.doc_type], name=SUBTYPES[document.kind])
    for note in document.notes:
        _el(root, CBC, "Note", note, languageID="en")
    _el(root, CBC, "DocumentCurrencyCode", currency)
    _el(root, CBC, "TaxCurrencyCode", currency)
    if document.po_number:
        _el(_el(root, CAC, "OrderReference"), CBC, "ID", document.po_number)
    if document.billing_reference:
        reference = _el(root, CAC, "BillingReference")
        _el(_el(reference, CAC, "InvoiceDocumentReference"), CBC, "ID", document.billing_reference)

    icv = _el(root, CAC, "AdditionalDocumentReference")
    _el(icv, CBC, "ID", "ICV")
    _el(icv, CBC, "UUID", str(document.icv))
    pih = _el(root, CAC, "AdditionalDocumentReference")
    _el(pih, CBC, "ID", "PIH")
    _el(_el(pih, CAC, "Attachment"), CBC, "EmbeddedDocumentBinaryObject", document.pih, mimeCode="text/plain")

    _seller(root, document.seller)
    _buyer(root, document.buyer, document.kind)
    _el(_el(root, CAC, "Delivery"), CBC, "ActualDeliveryDate", document.issued_at.strftime("%Y-%m-%d"))
    means = _el(root, CAC, "PaymentMeans")
    _el(means, CBC, "PaymentMeansCode", PAYMENT_MEANS.get(document.payment_method, "1"))
    if document.doc_type == "credit_note":
        _el(means, CBC, "InstructionNote", document.reason or "Order cancelled")

    _amount(_el(root, CAC, "TaxTotal"), "TaxAmount", document.vat_total, currency)
    tax_total = _el(root, CAC, "TaxTotal")
    _amount(tax_total, "TaxAmount", document.vat_total, currency)
    subtotal = _el(tax_total, CAC, "TaxSubtotal")
    _amount(subtotal, "TaxableAmount", document.taxable_amount, currency)
    _amount(subtotal, "TaxAmount", document.vat_total, currency)
    _tax_category(subtotal, "TaxCategory", document.vat_rate)

    monetary = _el(root, CAC, "LegalMonetaryTotal")
    _amount(monetary, "LineExtensionAmount", document.taxable_amount, currency)
    _amount(monetary, "TaxExclusiveAmount", document.taxable_amount, currency)
    _amount(monetary, "TaxInclusiveAmount", document.taxable_amount + document.vat_total, currency)
    _amount(monetary, "AllowanceTotalAmount", 0, currency)
    _amount(monetary, "PrepaidAmount", 0, currency)
    _amount(monetary, "PayableAmount", document.payable, currency)

    for index, line in enumerate(document.lines, start=1):
        element = _el(root, CAC, "InvoiceLine")
        _el(element, CBC, "ID", index)
        _el(element, CBC, "InvoicedQuantity", f"{line.quantity:.6f}", unitCode="PCE")
        _amount(element, "LineExtensionAmount", line.net, currency)
        line_tax = _el(element, CAC, "TaxTotal")
        _amount(line_tax, "TaxAmount", line.vat, currency)
        _amount(line_tax, "RoundingAmount", line.net + line.vat, currency)
        item = _el(element, CAC, "Item")
        _el(item, CBC, "Name", line.name)
        _tax_category(item, "ClassifiedTaxCategory", line.vat_rate)
        _amount(_el(element, CAC, "Price"), "PriceAmount", line.unit_price, currency)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
