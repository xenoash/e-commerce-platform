from decimal import Decimal

from lxml import etree

from .builder import CAC, CBC

NS = {"cac": CAC, "cbc": CBC}


def _text(node, path):
    if node is None:
        return ""
    element = node.find(path, NS)
    return element.text if element is not None and element.text else ""


def _address(party):
    address = party.find("cac:PostalAddress", NS) if party is not None else None
    if address is None:
        return None
    return {
        "street": _text(address, "cbc:StreetName"),
        "building_number": _text(address, "cbc:BuildingNumber"),
        "district": _text(address, "cbc:CitySubdivisionName"),
        "city": _text(address, "cbc:CityName"),
        "postal_code": _text(address, "cbc:PostalZone"),
        "country": _text(address, "cac:Country/cbc:IdentificationCode"),
    }


def read_invoice(xml):
    root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
    buyer = root.find("cac:AccountingCustomerParty/cac:Party", NS)
    return {
        "po_number": _text(root, "cac:OrderReference/cbc:ID"),
        "billing_reference": _text(root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID"),
        "buyer": {
            "name": _text(buyer, "cac:PartyLegalEntity/cbc:RegistrationName"),
            "vat_number": _text(buyer, "cac:PartyTaxScheme/cbc:CompanyID"),
            "cr_number": _text(buyer, "cac:PartyIdentification/cbc:ID"),
            "address": _address(buyer),
        },
        "lines": [
            {
                "name": _text(line, "cac:Item/cbc:Name"),
                "quantity": int(Decimal(_text(line, "cbc:InvoicedQuantity"))),
                "unit_price": Decimal(_text(line, "cac:Price/cbc:PriceAmount")),
                "net": Decimal(_text(line, "cbc:LineExtensionAmount")),
                "vat_rate": Decimal(_text(line, "cac:Item/cac:ClassifiedTaxCategory/cbc:Percent")),
                "vat": Decimal(_text(line, "cac:TaxTotal/cbc:TaxAmount")),
                "total": Decimal(_text(line, "cac:TaxTotal/cbc:RoundingAmount")),
            }
            for line in root.findall("cac:InvoiceLine", NS)
        ],
    }
