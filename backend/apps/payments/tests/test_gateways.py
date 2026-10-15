import json
from decimal import Decimal

import pytest
import responses
from django.conf import settings

from apps.payments.base import GatewayContext, InvalidSignature, PaymentRequest, PaymentStatus
from apps.payments.gateways.cod import CashOnDeliveryGateway
from apps.payments.gateways.fakepay import SIGNATURE_HEADER, FakepayGateway, sign_payload
from apps.payments.gateways.net_terms import NetTermsGateway
from apps.payments.gateways.tap import TapGateway, hashstring
from apps.payments.models import Payment, SimulatedCharge, WebhookEvent
from conftest import checkout, ready_cart

TAP_SECRET = "sk_test_contract"


def make_request(reference, token="tok_success", amount="115.00"):
    return PaymentRequest(
        reference=reference,
        amount=Decimal(amount),
        currency="SAR",
        method="card",
        description="Order ORD-1",
        return_url="https://shop.example.com/orders/1",
        webhook_url="https://api.example.com/webhooks",
        token=token,
        customer_email="buyer@example.com",
        metadata={"order_number": "ORD-1"},
    )


def tap_charge(charge_id, status, reference, url=None):
    return {
        "id": charge_id,
        "status": status,
        "amount": 115.0,
        "currency": "SAR",
        "reference": {"transaction": reference},
        "transaction": {"url": url, "created": "1760000000000"},
        "response": {"code": "000", "message": "Captured"},
    }


@pytest.fixture
def tap_api(monkeypatch):
    monkeypatch.setenv("TAP_SECRET_KEY", TAP_SECRET)
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        base = settings.TAP_API_BASE_URL
        mock.post(f"{base}/charges", json=tap_charge("chg_1", "CAPTURED", "ref-contract"))
        mock.get(f"{base}/charges/chg_1", json=tap_charge("chg_1", "CAPTURED", "ref-contract"))
        yield mock


GATEWAYS = {
    "cod": (CashOnDeliveryGateway, PaymentStatus.DEFERRED),
    "net_terms": (NetTermsGateway, PaymentStatus.DEFERRED),
    "fakepay": (FakepayGateway, PaymentStatus.SUCCEEDED),
    "tap": (TapGateway, PaymentStatus.SUCCEEDED),
}


@pytest.mark.parametrize("key", GATEWAYS)
def test_gateway_contract(key, store, tap_api):
    gateway_class, expected = GATEWAYS[key]
    gateway = gateway_class(GatewayContext(store_id=str(store.pk), store_handle=store.handle, method="card"))
    created = gateway.create_payment(make_request("ref-contract"))
    retried = gateway.create_payment(make_request("ref-contract"))
    retrieved = gateway.retrieve("ref-contract", created.external_ref)
    assert created.status == expected
    assert retried.external_ref == created.external_ref
    assert retrieved.status == expected
    assert gateway.key in settings.PAYMENT_GATEWAYS


def fakepay(store):
    return FakepayGateway(GatewayContext(store_id=str(store.pk), store_handle=store.handle, method="card"))


@pytest.mark.parametrize(
    "token,status,code",
    [
        ("tok_success", PaymentStatus.SUCCEEDED, ""),
        ("tok_decline", PaymentStatus.FAILED, "card_declined"),
        ("tok_insufficient_funds", PaymentStatus.FAILED, "insufficient_funds"),
        ("tok_3ds", PaymentStatus.REQUIRES_ACTION, ""),
        ("not-a-token", PaymentStatus.FAILED, "invalid_token"),
    ],
)
def test_fakepay_outcomes(store, token, status, code):
    result = fakepay(store).create_payment(make_request(f"ref-{token}", token=token))
    assert (result.status, result.failure_code) == (status, code)


def test_fakepay_refuses_a_reference_reused_with_another_amount(store):
    from apps.payments.base import GatewayError

    gateway = fakepay(store)
    gateway.create_payment(make_request("ref-amount"))
    with pytest.raises(GatewayError):
        gateway.create_payment(make_request("ref-amount", amount="1.00"))


def test_unknown_reference_reconciles_as_failed(store):
    assert fakepay(store).retrieve("never-created").failure_code == "payment_not_found"


def test_tap_maps_three_d_secure_redirects(store, monkeypatch):
    monkeypatch.setenv("TAP_SECRET_KEY", TAP_SECRET)
    gateway = TapGateway(GatewayContext(store_id=str(store.pk), store_handle=store.handle, method="card"))
    with responses.RequestsMock() as mock:
        mock.post(
            f"{settings.TAP_API_BASE_URL}/charges",
            json=tap_charge("chg_2", "INITIATED", "ref-3ds", url="https://tap.example/3ds"),
        )
        result = gateway.create_payment(make_request("ref-3ds"))
    assert result.status == PaymentStatus.REQUIRES_ACTION
    assert result.next_action == {"type": "redirect", "url": "https://tap.example/3ds"}


def test_tap_outage_is_transient(store, monkeypatch):
    from apps.payments.base import GatewayError

    monkeypatch.setenv("TAP_SECRET_KEY", TAP_SECRET)
    gateway = TapGateway(GatewayContext(store_id=str(store.pk), store_handle=store.handle, method="card"))
    with responses.RequestsMock() as mock:
        mock.post(f"{settings.TAP_API_BASE_URL}/charges", status=503)
        with pytest.raises(GatewayError) as error:
            gateway.create_payment(make_request("ref-down"))
    assert error.value.transient is True


def test_tap_webhook_signature(store, monkeypatch):
    monkeypatch.setenv("TAP_SECRET_KEY", TAP_SECRET)
    gateway = TapGateway(GatewayContext(store_id=str(store.pk), store_handle=store.handle, method="card"))
    payload = tap_charge("chg_9", "CAPTURED", "ref-hook")
    body = json.dumps(payload).encode()
    event = gateway.parse_webhook(body, {"hashstring": hashstring(payload, TAP_SECRET)})
    assert (event.reference, event.result.status) == ("ref-hook", PaymentStatus.SUCCEEDED)
    with pytest.raises(InvalidSignature):
        gateway.parse_webhook(body, {"hashstring": "0" * 64})


def webhook(client, store, payment_id, status, *, event_id="evt_1", signature=None):
    body = json.dumps(
        {
            "id": event_id,
            "type": f"charge.{status}",
            "data": {"charge_id": "fp_ch_x", "reference": payment_id, "status": status, "failure_code": ""},
        }
    ).encode()
    return client.post(
        f"/api/v1/webhooks/payments/fakepay/{store.handle}",
        body,
        content_type="application/json",
        headers={SIGNATURE_HEADER: signature or sign_payload(store.pk, body)},
    )


@pytest.fixture
def pending_order(guest_cart, product):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    return checkout(client, cart_id, payment_token="tok_3ds").data


def test_signed_webhook_settles_the_order(store, pending_order, client_for, django_capture_on_commit_callbacks):
    client = client_for(store)
    with django_capture_on_commit_callbacks(execute=True):
        response = webhook(client, store, pending_order["payment"]["id"], "succeeded")
    assert response.json() == {"received": True, "outcome": "applied"}
    assert Payment.objects.get().status == "succeeded"


def test_duplicate_and_out_of_order_webhooks_are_harmless(store, pending_order, client_for):
    client = client_for(store)
    payment_id = pending_order["payment"]["id"]
    webhook(client, store, payment_id, "succeeded", event_id="evt_a")
    duplicate = webhook(client, store, payment_id, "succeeded", event_id="evt_a")
    late_failure = webhook(client, store, payment_id, "failed", event_id="evt_b")
    assert duplicate.json()["outcome"] == "duplicate"
    assert late_failure.json()["outcome"] == "applied"
    assert Payment.objects.get().status == "succeeded"
    assert WebhookEvent.objects.count() == 2


def test_forged_webhook_is_rejected(store, pending_order, client_for):
    response = webhook(client_for(store), store, pending_order["payment"]["id"], "succeeded", signature="t=1,v1=bad")
    assert (response.status_code, response.json()["code"]) == (401, "WEBHOOK_SIGNATURE_INVALID")
    assert Payment.objects.get().status == "requires_action"


def test_webhook_signed_for_another_store_is_rejected(store, other_store, pending_order, client_for):
    body = b"{}"
    response = client_for(store).post(
        f"/api/v1/webhooks/payments/fakepay/{store.handle}",
        body,
        content_type="application/json",
        headers={SIGNATURE_HEADER: sign_payload(other_store.pk, body)},
    )
    assert response.status_code == 401


def test_three_d_secure_simulator_page(store, pending_order, client):
    charge = SimulatedCharge.objects.get()
    page = client.get(f"/sim/fakepay/3ds/{charge.pk}")
    assert page.status_code == 200
    assert b"Approve" in page.content
    with responses.RequestsMock() as mock:
        mock.post(charge.webhook_url, status=200)
        redirect = client.post(f"/sim/fakepay/3ds/{charge.pk}", {"outcome": "approve"})
    assert redirect.status_code == 302
    assert SimulatedCharge.objects.get().status == "succeeded"
