import base64
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier

ZATCA_TEMPLATE_OID = ObjectIdentifier("1.3.6.1.4.1.311.20.2")
CERT_TEMPLATE_BY_ENVIRONMENT = {
    "fake": "PREZATCA-Code-Signing",
    "simulation": "PREZATCA-Code-Signing",
    "developer_portal": "TSTZATCA-Code-Signing",
    "production": "ZATCA-Code-Signing",
}


def generate_private_key():
    return ec.generate_private_key(ec.SECP256K1())


def private_key_pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def load_private_key(pem):
    return serialization.load_pem_private_key(pem.encode(), password=None)


def certificate_from_b64(certificate_b64):
    return x509.load_der_x509_certificate(base64.b64decode(certificate_b64))


def certificate_b64(certificate):
    return base64.b64encode(certificate.public_bytes(serialization.Encoding.DER)).decode()


def self_signed_certificate(key, *, common_name, organization, vat_number, days=365):
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "SA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, vat_number[:10]),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local-ZATCA-Simulator-CA")])
    now = datetime.now(UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )


def build_csr(
    key,
    *,
    common_name,
    organization,
    organization_unit,
    vat_number,
    serial_number,
    environment,
    invoice_types="1100",
    address,
    business_category,
):
    template = CERT_TEMPLATE_BY_ENVIRONMENT[environment]
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "SA"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, organization_unit),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    directory = x509.Name(
        [
            x509.NameAttribute(ObjectIdentifier("2.5.4.4"), serial_number),
            x509.NameAttribute(NameOID.USER_ID, vat_number),
            x509.NameAttribute(NameOID.TITLE, invoice_types),
            x509.NameAttribute(ObjectIdentifier("2.5.4.26"), address),
            x509.NameAttribute(NameOID.BUSINESS_CATEGORY, business_category),
        ]
    )
    template_value = b"\x13" + bytes([len(template)]) + template.encode()
    return (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(x509.UnrecognizedExtension(ZATCA_TEMPLATE_OID, template_value), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.DirectoryName(directory)]), critical=False)
        .sign(key, hashes.SHA256())
    )


def csr_b64(csr):
    pem = csr.public_bytes(serialization.Encoding.PEM)
    return base64.b64encode(pem).decode()
