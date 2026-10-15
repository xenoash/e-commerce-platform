import hashlib
import hmac
import json
import os
from decimal import Decimal

import requests
from django.conf import settings

from ..base import (
    GatewayError,
    InvalidSignature,
    PaymentGateway,
    PaymentResult,
    PaymentStatus,
    RefundResult,
    WebhookEvent,
)

STATUS_MAP = {
    "CAPTURED": PaymentStatus.SUCCEEDED,
    "AUTHORIZED": PaymentStatus.PENDING,
    "INITIATED": PaymentStatus.REQUIRES_ACTION,
    "IN_PROGRESS": PaymentStatus.PENDING,
    "PENDING": PaymentStatus.PENDING,
    "FAILED": PaymentStatus.FAILED,
    "DECLINED": PaymentStatus.FAILED,
    "ABANDONED": PaymentStatus.FAILED,
    "CANCELLED": PaymentStatus.FAILED,
    "RESTRICTED": PaymentStatus.FAILED,
    "TIMEDOUT": PaymentStatus.FAILED,
    "VOID": PaymentStatus.FAILED,
    "UNKNOWN": PaymentStatus.FAILED,
}


def hashstring(payload, secret):
    reference = payload.get("reference") or {}
    canonical = (
        f"x_id{payload.get('id', '')}"
        f"x_amount{Decimal(str(payload.get('amount', '0'))):.2f}"
        f"x_currency{payload.get('currency', '')}"
        f"x_gateway_reference{reference.get('gateway', '')}"
        f"x_payment_reference{reference.get('payment', '')}"
        f"x_status{payload.get('status', '')}"
        f"x_created{(payload.get('transaction') or {}).get('created', '')}"
    )
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def result_from_charge(charge):
    status = STATUS_MAP.get(str(charge.get("status", "")).upper(), PaymentStatus.PENDING)
    transaction_url = (charge.get("transaction") or {}).get("url")
    if status == PaymentStatus.REQUIRES_ACTION and not transaction_url:
        status = PaymentStatus.PENDING
    response = charge.get("response") or {}
    return PaymentResult(
        status=status,
        external_ref=charge.get("id", ""),
        next_action={"type": "redirect", "url": transaction_url} if status == PaymentStatus.REQUIRES_ACTION else None,
        failure_code=str(response.get("code", "")) if status == PaymentStatus.FAILED else "",
        failure_message=str(response.get("message", "")) if status == PaymentStatus.FAILED else "",
    )


class TapGateway(PaymentGateway):
    key = "tap"
    supported_methods = frozenset({"card", "apple_pay"})
    requires_token = True

    @property
    def secret(self):
        name = self.context.config.get("secret_env", "TAP_SECRET_KEY")
        secret = os.environ.get(name, "")
        if not secret:
            raise GatewayError(f"Tap secret key {name} is not configured.", transient=False)
        return secret

    def _request(self, method, path, **kwargs):
        try:
            response = requests.request(
                method,
                f"{settings.TAP_API_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {self.secret}", "Accept": "application/json"},
                timeout=settings.PAYMENT_GATEWAY_TIMEOUT_SECONDS,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise GatewayError(f"Tap unreachable: {exc}", transient=True) from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise GatewayError(f"Tap returned {response.status_code}", transient=True)
        if response.status_code >= 400:
            raise GatewayError(f"Tap rejected the request: {response.text[:200]}", transient=False)
        return response.json()

    def create_payment(self, request):
        body = {
            "amount": float(request.amount),
            "currency": request.currency,
            "threeDSecure": True,
            "customer_initiated": True,
            "save_card": False,
            "description": request.description,
            "source": {"id": request.token},
            "customer": {"first_name": "Customer", "email": request.customer_email or ""},
            "reference": {"transaction": request.reference, "order": request.metadata.get("order_number", "")},
            "metadata": request.metadata,
            "redirect": {"url": request.return_url},
            "post": {"url": request.webhook_url},
        }
        return result_from_charge(self._request("POST", "/charges", json=body))

    def retrieve(self, reference, external_ref=""):
        if not external_ref:
            return PaymentResult(PaymentStatus.PENDING)
        return result_from_charge(self._request("GET", f"/charges/{external_ref}"))

    def refund(self, reference, amount):
        from apps.payments.models import Payment

        payment = Payment.objects.get(pk=reference)
        data = self._request(
            "POST",
            "/refunds",
            json={
                "charge_id": payment.external_ref,
                "amount": float(amount),
                "currency": payment.currency,
                "reason": "requested_by_customer",
                "reference": {"merchant": f"rfnd-{reference}"},
            },
        )
        return RefundResult(succeeded=data.get("status") in {"REFUNDED", "PENDING"}, external_ref=data.get("id", ""))

    def parse_webhook(self, body, headers):
        payload = json.loads(body or b"{}")
        received = headers.get("hashstring", "")
        if not received or not hmac.compare_digest(hashstring(payload, self.secret), received):
            raise InvalidSignature("Tap hashstring mismatch.")
        if not str(payload.get("id", "")).startswith("chg_"):
            return None
        reference = (payload.get("reference") or {}).get("transaction", "")
        return WebhookEvent(
            event_id=f"{payload['id']}:{payload.get('status', '')}",
            reference=reference,
            result=result_from_charge(payload),
        )
