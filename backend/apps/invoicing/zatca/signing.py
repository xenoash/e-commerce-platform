import base64
import hashlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from lxml import etree

from . import qr
from .builder import CAC, CBC
from .crypto import certificate_from_b64, load_private_key

FIRST_PREVIOUS_HASH = base64.b64encode(hashlib.sha256(b"0").hexdigest().encode()).decode()

STRIP_SIGNATURE_XSL = b"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <xsl:output omit-xml-declaration="yes" indent="no" encoding="utf-8"/>
  <xsl:template match="node() | @*">
    <xsl:copy><xsl:apply-templates select="node() | @*"/></xsl:copy>
  </xsl:template>
  <xsl:template match="//*[local-name()='Invoice']//*[local-name()='UBLExtensions']"/>
  <xsl:template match="//*[local-name()='AdditionalDocumentReference'][cbc:ID[normalize-space(text()) = 'QR']]"/>
  <xsl:template match="//*[local-name()='Invoice']//*[local-name()='Signature']"/>
</xsl:stylesheet>"""
_STRIP = etree.XSLT(etree.fromstring(STRIP_SIGNATURE_XSL))

SIGNATURE_INDENT = " " * 32

UBL_EXTENSIONS_TEMPLATE = """<ext:UBLExtensions xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">
    <ext:UBLExtension>
        <ext:ExtensionURI>urn:oasis:names:specification:ubl:dsig:enveloped:xades</ext:ExtensionURI>
        <ext:ExtensionContent>
            <sig:UBLDocumentSignatures xmlns:sig="urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2" xmlns:sac="urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2" xmlns:sbc="urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2">
                <sac:SignatureInformation>
                    <cbc:ID>urn:oasis:names:specification:ubl:signature:1</cbc:ID>
                    <sbc:ReferencedSignatureID>urn:oasis:names:specification:ubl:signature:Invoice</sbc:ReferencedSignatureID>
                    <ds:Signature Id="signature" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                        <ds:SignedInfo>
                            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2006/12/xml-c14n11"/>
                            <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"/>
                            <ds:Reference Id="invoiceSignedData" URI="">
                                <ds:Transforms>
                                    <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
                                        <ds:XPath>not(//ancestor-or-self::ext:UBLExtensions)</ds:XPath>
                                    </ds:Transform>
                                    <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
                                        <ds:XPath>not(//ancestor-or-self::cac:Signature)</ds:XPath>
                                    </ds:Transform>
                                    <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
                                        <ds:XPath>not(//ancestor-or-self::cac:AdditionalDocumentReference[cbc:ID='QR'])</ds:XPath>
                                    </ds:Transform>
                                    <ds:Transform Algorithm="http://www.w3.org/2006/12/xml-c14n11"/>
                                </ds:Transforms>
                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                                <ds:DigestValue>{invoice_hash}</ds:DigestValue>
                            </ds:Reference>
                            <ds:Reference Type="http://www.w3.org/2000/09/xmldsig#SignatureProperties" URI="#xadesSignedProperties">
                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                                <ds:DigestValue>{signed_properties_digest}</ds:DigestValue>
                            </ds:Reference>
                        </ds:SignedInfo>
                        <ds:SignatureValue>{signature}</ds:SignatureValue>
                        <ds:KeyInfo>
                            <ds:X509Data>
                                <ds:X509Certificate>{certificate}</ds:X509Certificate>
                            </ds:X509Data>
                        </ds:KeyInfo>
                        <ds:Object>
                            <xades:QualifyingProperties Target="signature" xmlns:xades="http://uri.etsi.org/01903/v1.3.2#">
                                {signed_properties}
                            </xades:QualifyingProperties>
                        </ds:Object>
                    </ds:Signature>
                </sac:SignatureInformation>
            </sig:UBLDocumentSignatures>
        </ext:ExtensionContent>
    </ext:UBLExtension>
</ext:UBLExtensions>"""

SIGNED_PROPERTIES_LINES = (
    '<xades:SignedProperties{xmlns} Id="xadesSignedProperties">',
    "    <xades:SignedSignatureProperties>",
    "        <xades:SigningTime>{signing_time}</xades:SigningTime>",
    "        <xades:SigningCertificate>",
    "            <xades:Cert>",
    "                <xades:CertDigest>",
    '                    <ds:DigestMethod{ds} Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>',
    "                    <ds:DigestValue{ds}>{cert_digest}</ds:DigestValue>",
    "                </xades:CertDigest>",
    "                <xades:IssuerSerial>",
    "                    <ds:X509IssuerName{ds}>{issuer}</ds:X509IssuerName>",
    "                    <ds:X509SerialNumber{ds}>{serial}</ds:X509SerialNumber>",
    "                </xades:IssuerSerial>",
    "            </xades:Cert>",
    "        </xades:SigningCertificate>",
    "    </xades:SignedSignatureProperties>",
    "</xades:SignedProperties>",
)

QR_AND_SIGNATURE_TEMPLATE = (
    "<cac:AdditionalDocumentReference>"
    "<cbc:ID>QR</cbc:ID>"
    '<cac:Attachment><cbc:EmbeddedDocumentBinaryObject mimeCode="text/plain">{qr}</cbc:EmbeddedDocumentBinaryObject></cac:Attachment>'
    "</cac:AdditionalDocumentReference>"
    "<cac:Signature>"
    "<cbc:ID>urn:oasis:names:specification:ubl:signature:Invoice</cbc:ID>"
    "<cbc:SignatureMethod>urn:oasis:names:specification:ubl:dsig:enveloped:xades</cbc:SignatureMethod>"
    "</cac:Signature>"
)


@dataclass(frozen=True)
class SignedInvoice:
    xml: str
    invoice_hash: str
    signature: str
    qr: str


def canonical_invoice(xml):
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(xml if isinstance(xml, bytes) else xml.encode(), parser)
    return etree.tostring(_STRIP(root), method="c14n")


def invoice_hash(xml):
    return base64.b64encode(hashlib.sha256(canonical_invoice(xml)).digest()).decode()


def _b64_hex_sha256(data):
    return base64.b64encode(hashlib.sha256(data).hexdigest().encode()).decode()


def issuer_name(certificate):
    common_names = [a.value for a in certificate.issuer if a.oid._name == "commonName"]
    domain_components = [a.value for a in certificate.issuer if a.oid._name == "domainComponent"]
    parts = [f"CN={common_names[0]}"] if common_names else []
    parts.extend(f"DC={component}" for component in reversed(domain_components) if component)
    return ", ".join(parts)


def _signed_properties(*, signing_time, cert_digest, issuer, serial, embedded):
    ds_ns = "" if embedded else ' xmlns:ds="http://www.w3.org/2000/09/xmldsig#"'
    xades_ns = "" if embedded else ' xmlns:xades="http://uri.etsi.org/01903/v1.3.2#"'
    lines = [
        line.format(
            xmlns=xades_ns, ds=ds_ns, signing_time=signing_time, cert_digest=cert_digest, issuer=issuer, serial=serial
        )
        for line in SIGNED_PROPERTIES_LINES
    ]
    return lines[0] + "".join("\n" + SIGNATURE_INDENT + line for line in lines[1:])


def _element_text(root, path):
    element = root.find(path)
    return element.text if element is not None and element.text else ""


def build_qr(canonical_root, *, invoice_hash_b64, signature_b64, certificate, include_certificate_signature):
    party = f"{{{CAC}}}AccountingSupplierParty/{{{CAC}}}Party"
    fields = [
        (qr.SELLER_NAME, _element_text(canonical_root, f"{party}/{{{CAC}}}PartyLegalEntity/{{{CBC}}}RegistrationName")),
        (qr.VAT_NUMBER, _element_text(canonical_root, f"{party}/{{{CAC}}}PartyTaxScheme/{{{CBC}}}CompanyID")),
        (
            qr.TIMESTAMP,
            f"{_element_text(canonical_root, f'{{{CBC}}}IssueDate')}T{_element_text(canonical_root, f'{{{CBC}}}IssueTime')}",
        ),
        (qr.INVOICE_TOTAL, _element_text(canonical_root, f"{{{CAC}}}LegalMonetaryTotal/{{{CBC}}}TaxInclusiveAmount")),
        (qr.VAT_TOTAL, _element_text(canonical_root, f"{{{CAC}}}TaxTotal/{{{CBC}}}TaxAmount")),
        (qr.INVOICE_HASH, invoice_hash_b64),
        (qr.SIGNATURE, signature_b64),
        (
            qr.PUBLIC_KEY,
            certificate.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            ),
        ),
    ]
    if include_certificate_signature:
        fields.append((qr.CERTIFICATE_SIGNATURE, certificate.signature))
    return qr.encode_tlv(fields)


def sign_invoice(unsigned_xml, *, private_key_pem, certificate_b64, signing_time, include_certificate_signature):
    parser = etree.XMLParser(remove_blank_text=False)
    pretty = etree.tostring(etree.fromstring(unsigned_xml, parser), pretty_print=True, encoding="UTF-8")
    canonical = canonical_invoice(pretty).decode()
    digest_b64 = base64.b64encode(hashlib.sha256(canonical.encode()).digest()).decode()

    certificate = certificate_from_b64(certificate_b64)
    signature_b64 = base64.b64encode(
        load_private_key(private_key_pem).sign(base64.b64decode(digest_b64), ec.ECDSA(hashes.SHA256()))
    ).decode()
    cert_digest = _b64_hex_sha256(certificate_b64.encode())
    properties = {
        "signing_time": signing_time,
        "cert_digest": cert_digest,
        "issuer": issuer_name(certificate),
        "serial": certificate.serial_number,
    }
    signed_properties_digest = _b64_hex_sha256(_signed_properties(**properties, embedded=False).encode())
    canonical_root = etree.fromstring(canonical.encode())
    qr_b64 = build_qr(
        canonical_root,
        invoice_hash_b64=digest_b64,
        signature_b64=signature_b64,
        certificate=certificate,
        include_certificate_signature=include_certificate_signature,
    )

    extensions = UBL_EXTENSIONS_TEMPLATE.format(
        invoice_hash=digest_b64,
        signed_properties_digest=signed_properties_digest,
        signature=signature_b64,
        certificate=certificate_b64,
        signed_properties=_signed_properties(**properties, embedded=True),
    )
    after_root_tag = canonical.index(">") + 1
    signed = canonical[:after_root_tag] + extensions + canonical[after_root_tag:]
    anchor = signed.index("<cac:AccountingSupplierParty>")
    signed = signed[:anchor] + QR_AND_SIGNATURE_TEMPLATE.format(qr=qr_b64) + signed[anchor:]
    signed_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + signed

    if invoice_hash(signed_xml.encode()) != digest_b64:
        raise RuntimeError("Signed invoice no longer hashes to its digest; refusing to emit it.")
    return SignedInvoice(xml=signed_xml, invoice_hash=digest_b64, signature=signature_b64, qr=qr_b64)


def verify_signed_invoice(signed_xml):
    root = etree.fromstring(signed_xml.encode() if isinstance(signed_xml, str) else signed_xml)
    ds = "{http://www.w3.org/2000/09/xmldsig#}"
    declared_hash = root.find(f".//{ds}Reference[@Id='invoiceSignedData']/{ds}DigestValue").text
    signature = root.find(f".//{ds}SignatureValue").text
    certificate = certificate_from_b64(root.find(f".//{ds}X509Certificate").text)
    actual_hash = invoice_hash(signed_xml if isinstance(signed_xml, bytes) else signed_xml.encode())
    if actual_hash != declared_hash:
        return False, "Invoice hash does not match the document."
    try:
        certificate.public_key().verify(
            base64.b64decode(signature), base64.b64decode(declared_hash), ec.ECDSA(hashes.SHA256())
        )
    except InvalidSignature:
        return False, "Signature does not verify against the certificate."
    return True, ""
