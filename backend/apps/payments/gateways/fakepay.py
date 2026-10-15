import hashlib
import hmac
import json
import secrets
import time

from django.conf import settings
from django.db import IntegrityError, transaction

from ..base import (
    GatewayError,
    InvalidSignature,
    PaymentGateway,
    PaymentResult,
    PaymentStatus,
    RefundResult,
    WebhookEvent,
)
from ..models import SimulatedCharge

SIGNATURE_HEADER = "X-Fakepay-Signature"
SIGNATURE_TOLERANCE_SECONDS = 300

TOKEN_OUTCOMES = {
    "tok_success": (SimulatedCharge.Status.SUCCEEDED, ""),
    "tok_applepay": (SimulatedCharge.Status.SUCCEEDED, ""),
    "tok_decline": (SimulatedCharge.Status.FAILED, "card_declined"),
    "tok_insufficient_funds": (SimulatedCharge.Status.FAILED, "insufficient_funds"),
    "tok_3ds": (SimulatedCharge.Status.REQUIRES_ACTION, ""),
    "tok_timeout": (SimulatedCharge.Status.SUCCEEDED, ""),
}
FAILURE_MESSAGES = {
    "card_declined": "The card was declined.",
    "insufficient_funds": "The card has insufficient funds.",
    "authentication_failed": "3-D Secure authentication failed.",
    "payment_not_found": "The gateway has no record of this payment.",
}


def webhook_secret(store_id):
    return hmac.new(settings.SECRET_KEY.encode(), f"fakepay-webhook:{store_id}".encode(), hashlib.sha256).hexdigest()


def sign_payload(store_id, body, timestamp=None):
    timestamp = int(timestamp or time.time())
    digest = hmac.new(webhook_secret(store_id).encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def challenge_url(charge_id):
    return f"{settings.PUBLIC_API_URL}/sim/fakepay/3ds/{charge_id}"


def result_for(charge):
    if charge.status == SimulatedCharge.Status.SUCCEEDED:
        return PaymentResult(PaymentStatus.SUCCEEDED, external_ref=charge.id)
    if charge.status == SimulatedCharge.Status.REQUIRES_ACTION:
        return PaymentResult(
            PaymentStatus.REQUIRES_ACTION,
            external_ref=charge.id,
            next_action={"type": "redirect", "url": challenge_url(charge.id)},
        )
    if charge.status == SimulatedCharge.Status.REFUNDED:
        return PaymentResult(PaymentStatus.SUCCEEDED, external_ref=charge.id)
    code = charge.failure_code or "card_declined"
    return PaymentResult(
        PaymentStatus.FAILED,
        external_ref=charge.id,
        failure_code=code,
        failure_message=FAILURE_MESSAGES.get(code, "The payment failed."),
    )


class FakepayGateway(PaymentGateway):
    key = "fakepay"
    supported_methods = frozenset({"card", "apple_pay"})
    requires_token = True

    def create_payment(self, request):
        outcome = TOKEN_OUTCOMES.get(request.token or "")
        if outcome is None:
            return PaymentResult(
                PaymentStatus.FAILED, failure_code="invalid_token", failure_message="The payment token is not valid."
            )
        charge = SimulatedCharge.objects.filter(reference=request.reference).first()
        if charge is None:
            status, failure_code = outcome
            try:
                with transaction.atomic():
                    charge = SimulatedCharge.objects.create(
                        id=f"fp_ch_{secrets.token_hex(10)}",
                        store_id=self.context.store_id,
                        store_handle=self.context.store_handle,
                        reference=request.reference,
                        amount=request.amount,
                        currency=request.currency,
                        token=request.token,
                        status=status,
                        failure_code=failure_code,
                        return_url=request.return_url,
                        webhook_url=request.webhook_url,
                    )
            except IntegrityError:
                charge = SimulatedCharge.objects.get(reference=request.reference)
        if charge.amount != request.amount:
            raise GatewayError("Reference reused with a different amount.", transient=False)
        if request.token == "tok_timeout" and charge.status == SimulatedCharge.Status.SUCCEEDED:
            raise GatewayError("Gateway timed out after accepting the charge.", transient=True)
        return result_for(charge)

    def retrieve(self, reference, external_ref=""):
        charge = SimulatedCharge.objects.filter(reference=reference).first()
        if charge is None:
            return PaymentResult(
                PaymentStatus.FAILED,
                failure_code="payment_not_found",
                failure_message=FAILURE_MESSAGES["payment_not_found"],
            )
        return result_for(charge)

    def refund(self, reference, amount):
        updated = SimulatedCharge.objects.filter(reference=reference, status=SimulatedCharge.Status.SUCCEEDED).update(
            status=SimulatedCharge.Status.REFUNDED
        )
        return RefundResult(succeeded=bool(updated), external_ref=f"fp_re_{reference}")

    def parse_webhook(self, body, headers):
        header = headers.get(SIGNATURE_HEADER, "")
        parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
        try:
            timestamp = int(parts.get("t", ""))
        except ValueError as exc:
            raise InvalidSignature("Missing timestamp.") from exc
        if abs(time.time() - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
            raise InvalidSignature("Signature timestamp is outside the tolerance window.")
        expected = sign_payload(self.context.store_id, body, timestamp).split("v1=", 1)[1]
        if not hmac.compare_digest(expected, parts.get("v1", "")):
            raise InvalidSignature("Signature mismatch.")
        payload = json.loads(body)
        if not payload.get("type", "").startswith("charge."):
            return None
        data = payload["data"]
        charge = SimulatedCharge(
            id=data["charge_id"],
            status=data["status"],
            failure_code=data.get("failure_code", ""),
        )
        return WebhookEvent(event_id=payload["id"], reference=data["reference"], result=result_for(charge))
