import base64
import logging
from dataclasses import dataclass, field
from enum import StrEnum

import requests
from django.conf import settings

from .signing import verify_signed_invoice

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


class Outcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RETRY = "retry"


@dataclass(frozen=True)
class SubmissionResult:
    outcome: Outcome
    status_label: str = ""
    http_status: int | None = None
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    cleared_xml: str = ""


class FakeZatcaClient:
    def __init__(self, device):
        self.device = device

    def _verify(self, signed_xml):
        valid, reason = verify_signed_invoice(signed_xml)
        if valid:
            return None
        return SubmissionResult(
            Outcome.REJECTED, "NOT_REPORTED", 400, errors=[{"code": "invalid-signature", "message": reason}]
        )

    def report(self, *, invoice_hash, uuid, signed_xml):
        return self._verify(signed_xml) or SubmissionResult(Outcome.ACCEPTED, "REPORTED", 200)

    def clear(self, *, invoice_hash, uuid, signed_xml):
        rejected = self._verify(signed_xml)
        if rejected:
            return SubmissionResult(Outcome.REJECTED, "NOT_CLEARED", 400, errors=rejected.errors)
        return SubmissionResult(Outcome.ACCEPTED, "CLEARED", 200, cleared_xml=signed_xml)


class HttpZatcaClient:
    def __init__(self, device, base_url):
        self.device = device
        self.base_url = base_url.rstrip("/")

    def _post(self, path, *, clearance, invoice_hash, uuid, signed_xml):
        credentials = base64.b64encode(
            f"{self.device.binary_security_token}:{self.device.api_secret}".encode()
        ).decode()
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en",
            "Accept-Version": "V2",
            "Clearance-Status": "1" if clearance else "0",
            "Authorization": f"Basic {credentials}",
        }
        body = {
            "invoiceHash": invoice_hash,
            "uuid": uuid,
            "invoice": base64.b64encode(signed_xml.encode()).decode(),
        }
        try:
            response = requests.post(
                f"{self.base_url}{path}", json=body, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            logger.warning("zatca_unreachable error=%s", exc)
            return None, None
        try:
            return response, response.json()
        except ValueError:
            return response, None

    def report(self, *, invoice_hash, uuid, signed_xml):
        response, payload = self._post(
            "/invoices/reporting/single", clearance=False, invoice_hash=invoice_hash, uuid=uuid, signed_xml=signed_xml
        )
        return classify(response, payload, status_key="reportingStatus", accepted_label="REPORTED")

    def clear(self, *, invoice_hash, uuid, signed_xml):
        response, payload = self._post(
            "/invoices/clearance/single", clearance=True, invoice_hash=invoice_hash, uuid=uuid, signed_xml=signed_xml
        )
        result = classify(response, payload, status_key="clearanceStatus", accepted_label="CLEARED")
        if result.outcome == Outcome.ACCEPTED and payload.get("clearedInvoice"):
            cleared = base64.b64decode(payload["clearedInvoice"]).decode()
            return SubmissionResult(
                result.outcome, result.status_label, result.http_status, result.warnings, [], cleared
            )
        return result


def _messages(payload, key):
    results = (payload or {}).get("validationResults") or {}
    return [
        {"code": item.get("code", ""), "message": item.get("message", ""), "category": item.get("category", "")}
        for item in results.get(key) or []
    ]


def classify(response, payload, *, status_key, accepted_label):
    if response is None:
        return SubmissionResult(Outcome.RETRY, "UNREACHABLE")
    status = response.status_code
    if status == 429 or status >= 500 or payload is None:
        return SubmissionResult(Outcome.RETRY, "TRANSIENT", status)
    warnings = _messages(payload, "warningMessages")
    errors = _messages(payload, "errorMessages")
    label = payload.get(status_key, "")
    if status in (200, 202) and label == accepted_label:
        return SubmissionResult(Outcome.ACCEPTED, label, status, warnings)
    if status in (401, 403):
        return SubmissionResult(Outcome.RETRY, "UNAUTHORIZED", status, warnings, errors)
    return SubmissionResult(Outcome.REJECTED, label or "REJECTED", status, warnings, errors)


def client_for(device):
    if device.environment == device.Environment.FAKE:
        return FakeZatcaClient(device)
    if device.environment == device.Environment.SIMULATION:
        return HttpZatcaClient(device, settings.ZATCA_SIMULATION_URL)
    if device.environment == device.Environment.DEVELOPER_PORTAL:
        return HttpZatcaClient(device, settings.ZATCA_DEVELOPER_PORTAL_URL)
    raise ValueError(f"Unsupported ZATCA environment {device.environment}")
