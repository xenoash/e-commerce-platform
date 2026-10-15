import base64

MAX_TLV_VALUE_BYTES = 255

SELLER_NAME = 1
VAT_NUMBER = 2
TIMESTAMP = 3
INVOICE_TOTAL = 4
VAT_TOTAL = 5
INVOICE_HASH = 6
SIGNATURE = 7
PUBLIC_KEY = 8
CERTIFICATE_SIGNATURE = 9


def encode_tlv(fields):
    chunks = []
    for tag, value in fields:
        data = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        if len(data) > MAX_TLV_VALUE_BYTES:
            raise ValueError(f"QR tag {tag} is {len(data)} bytes; ZATCA allows at most {MAX_TLV_VALUE_BYTES}.")
        chunks.append(bytes([tag, len(data)]) + data)
    return base64.b64encode(b"".join(chunks)).decode("ascii")


def decode_tlv(encoded):
    raw = base64.b64decode(encoded)
    fields = {}
    position = 0
    while position < len(raw):
        tag, length = raw[position], raw[position + 1]
        fields[tag] = raw[position + 2 : position + 2 + length]
        position += 2 + length
    return fields
