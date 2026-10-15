from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.carts.models import Cart
from apps.catalog.models import Product
from apps.invoicing.models import Invoice
from apps.orders.lifecycle import apply_payment_result
from apps.orders.models import Order
from apps.orders.tasks import sweep_pending_orders
from apps.payments.base import PaymentResult, PaymentStatus
from apps.payments.models import Payment, SimulatedCharge
from apps.promotions.models import Coupon, CouponRedemption
from conftest import BILLING, CouponFactory, checkout, ready_cart


def stock_of(product):
    return Product.objects.get(pk=product.pk).stock


@pytest.fixture
def paid_flow(guest_cart, product, django_capture_on_commit_callbacks):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product, quantity=2)
    with django_capture_on_commit_callbacks(execute=True):
        response = checkout(client, cart_id, payment_token="tok_success")
    return client, cart_id, response


def test_successful_card_checkout(paid_flow, product):
    _, cart_id, response = paid_flow
    order = response.data
    assert response.status_code == 201
    assert response["Location"] == f"/api/v1/orders/{order['id']}"
    assert order["status"] == "paid"
    assert order["payment"]["status"] == "succeeded"
    assert order["totals"]["total"] == "900.00"
    assert stock_of(product) == 8
    assert Cart.objects.get(pk=cart_id).status == Cart.Status.CONVERTED
    invoice = Invoice.objects.get(order_id=order["id"])
    assert (invoice.kind, invoice.status, invoice.total) == ("simplified", "reported", Decimal("900.00"))


def test_order_snapshot_survives_catalogue_changes(paid_flow, product):
    client, _, response = paid_flow
    product.price = Decimal("1.00")
    product.name = "Renamed"
    product.save()
    order = client.get(f"/api/v1/orders/{response.data['id']}").data
    assert order["lines"][0]["name"] == "Oud Royale"
    assert order["lines"][0]["unit_price"] == "450.00"


def test_three_d_secure_then_confirm(guest_cart, product, django_capture_on_commit_callbacks):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    order = checkout(client, cart_id, payment_token="tok_3ds").data
    assert order["status"] == "pending_payment"
    assert order["payment"]["status"] == "requires_action"
    assert "/sim/fakepay/3ds/" in order["payment"]["next_action"]["url"]
    assert Cart.objects.get(pk=cart_id).status == Cart.Status.CHECKING_OUT

    SimulatedCharge.objects.filter(reference=order["payment"]["id"]).update(status=SimulatedCharge.Status.SUCCEEDED)
    with django_capture_on_commit_callbacks(execute=True):
        confirmed = client.post(f"/api/v1/orders/{order['id']}/payment/confirm")
    again = client.post(f"/api/v1/orders/{order['id']}/payment/confirm")
    assert confirmed.data["status"] == "paid"
    assert again.data["status"] == "paid"
    assert Payment.objects.filter(order_id=order["id"]).count() == 1


def test_declined_card_releases_everything(guest_cart, product):
    client, cart_id = guest_cart
    CouponFactory(code="ONCE", usage_limit=1)
    ready_cart(client, cart_id, product, quantity=3)
    client.put(f"/api/v1/carts/{cart_id}/coupon", {"code": "ONCE"}, format="json")
    order = checkout(client, cart_id, payment_token="tok_decline").data
    assert order["status"] == "payment_failed"
    assert order["payment"]["failure_code"] == "card_declined"
    assert stock_of(product) == 10
    assert Coupon.objects.get(code="ONCE").times_used == 0
    assert CouponRedemption.objects.get().released_at is not None
    assert Cart.objects.get(pk=cart_id).status == Cart.Status.OPEN
    retry = checkout(client, cart_id, key="second-attempt-01", payment_token="tok_success")
    assert retry.status_code == 201
    assert retry.data["status"] == "paid"
    assert retry.data["number"] != order["number"]


def test_same_key_replays_without_a_second_order(paid_flow):
    client, cart_id, first = paid_flow
    replay = checkout(client, cart_id, payment_token="tok_success")
    assert replay.status_code == 201
    assert replay["Idempotent-Replayed"] == "true"
    assert replay.data["id"] == first.data["id"]
    assert Order.objects.count() == 1


def test_key_reused_with_a_different_body_is_rejected(paid_flow):
    client, cart_id, _ = paid_flow
    response = checkout(client, cart_id, payment_token="tok_applepay")
    assert (response.status_code, response.data["code"]) == (422, "IDEMPOTENCY_KEY_REUSED")


def test_checkout_requires_an_idempotency_key(guest_cart, product):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    missing = client.post(f"/api/v1/carts/{cart_id}/checkout", {}, format="json")
    malformed = client.post(f"/api/v1/carts/{cart_id}/checkout", {}, format="json", HTTP_IDEMPOTENCY_KEY="short")
    assert (missing.status_code, missing.data["code"]) == (428, "IDEMPOTENCY_KEY_REQUIRED")
    assert (malformed.status_code, malformed.data["code"]) == (400, "IDEMPOTENCY_KEY_INVALID")


def test_rejected_checkout_frees_the_key_for_a_retry(guest_cart, product):
    client, cart_id = guest_cart
    client.post(f"/api/v1/carts/{cart_id}/items", {"product_id": str(product.pk)}, format="json")
    not_ready = checkout(client, cart_id, payment_token="tok_success")
    assert (not_ready.status_code, not_ready.data["code"]) == (409, "CART_NOT_READY")
    assert not_ready.data["missing"] == ["shipping_address", "payment_method"]
    ready_cart(client, cart_id, product)
    retried = checkout(client, cart_id, payment_token="tok_success")
    assert retried.status_code == 201


def test_total_changed_since_the_shopper_looked(guest_cart, product):
    client, cart_id = guest_cart
    seen = ready_cart(client, cart_id, product)["totals"]["total"]
    product.price = Decimal("460.00")
    product.save()
    response = checkout(client, cart_id, payment_token="tok_success", expected_total=seen)
    assert (response.status_code, response.data["code"]) == (409, "CART_TOTAL_CHANGED")
    assert (response.data["expected_total"], response.data["current_total"]) == ("450.00", "460.00")
    assert stock_of(product) == 10


def test_coupon_that_stopped_applying_blocks_checkout(guest_cart, product):
    client, cart_id = guest_cart
    coupon = CouponFactory(code="SOON-GONE")
    ready_cart(client, cart_id, product)
    client.put(f"/api/v1/carts/{cart_id}/coupon", {"code": "SOON-GONE"}, format="json")
    Coupon.objects.filter(pk=coupon.pk).update(ends_at=timezone.now() - timedelta(minutes=1))
    response = checkout(client, cart_id, payment_token="tok_success")
    assert response.status_code == 409
    assert response.data["code"] in ("CART_NOT_READY", "COUPON_NOT_APPLICABLE")


def test_card_methods_need_a_token(guest_cart, product):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    response = checkout(client, cart_id)
    assert (response.status_code, response.data["code"]) == (422, "PAYMENT_TOKEN_REQUIRED")


def test_cash_on_delivery_confirms_without_charging(guest_cart, product, django_capture_on_commit_callbacks):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product, method="cod")
    with django_capture_on_commit_callbacks(execute=True):
        order = checkout(client, cart_id).data
    assert (order["status"], order["payment"]["status"]) == ("confirmed", "deferred")
    assert Invoice.objects.filter(order_id=order["id"]).exists()


def test_b2b_net_terms_with_standard_invoice(
    store, business_customer, client_for, product, django_capture_on_commit_callbacks
):
    client = client_for(store, customer=business_customer)
    cart_id = client.post("/api/v1/carts").data["id"]
    ready_cart(client, cart_id, product, quantity=2, method="net_terms")
    client.put(f"/api/v1/carts/{cart_id}/billing-address", BILLING, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        order = checkout(client, cart_id, po_number="PO-77").data
    assert (order["status"], order["invoice_kind"], order["po_number"]) == ("confirmed", "standard", "PO-77")
    invoice = client.get(f"/api/v1/orders/{order['id']}/invoice").data
    assert (invoice["kind"], invoice["status"]) == ("standard", "cleared")
    assert invoice["buyer"]["vat_number"] == "310175397400003"


def test_credit_limit_is_enforced(store, business_customer, client_for, product):
    business_customer.credit_limit = Decimal("1000.00")
    business_customer.save()
    client = client_for(store, customer=business_customer)
    cart_id = client.post("/api/v1/carts").data["id"]
    ready_cart(client, cart_id, product, quantity=3, method="net_terms")
    client.put(f"/api/v1/carts/{cart_id}/billing-address", BILLING, format="json")
    response = checkout(client, cart_id)
    assert (response.status_code, response.data["code"]) == (409, "CREDIT_LIMIT_EXCEEDED")
    assert response.data["available"] == "1000.00"
    assert stock_of(product) == 10


def test_gateway_timeout_is_reconciled_by_the_sweeper(guest_cart, product, django_capture_on_commit_callbacks):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    order = checkout(client, cart_id, payment_token="tok_timeout").data
    assert (order["status"], order["payment"]["status"]) == ("pending_payment", "pending")
    Order.objects.filter(pk=order["id"]).update(placed_at=timezone.now() - timedelta(minutes=5))
    with django_capture_on_commit_callbacks(execute=True):
        outcome = sweep_pending_orders()
    assert outcome == {"paid": 1}
    assert Order.objects.get(pk=order["id"]).status == "paid"


def test_abandoned_payment_expires_and_restocks(guest_cart, product):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product, quantity=4)
    order = checkout(client, cart_id, payment_token="tok_3ds").data
    assert stock_of(product) == 6
    Order.objects.filter(pk=order["id"]).update(
        placed_at=timezone.now() - timedelta(minutes=30), expires_at=timezone.now() - timedelta(minutes=1)
    )
    assert sweep_pending_orders() == {"expired": 1}
    assert stock_of(product) == 10
    assert Cart.objects.get(pk=cart_id).status == Cart.Status.OPEN
    assert Payment.objects.get(order_id=order["id"]).status == "cancelled"


def test_late_success_after_expiry_is_honoured_when_stock_allows(
    guest_cart, product, django_capture_on_commit_callbacks
):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    order = checkout(client, cart_id, payment_token="tok_3ds").data
    Order.objects.filter(pk=order["id"]).update(expires_at=timezone.now() - timedelta(minutes=1))
    from apps.orders.lifecycle import expire_order

    expire_order(order["id"])
    with django_capture_on_commit_callbacks(execute=True):
        apply_payment_result(order["payment"]["id"], PaymentResult(PaymentStatus.SUCCEEDED, external_ref="late"))
    assert Order.objects.get(pk=order["id"]).status == "paid"
    assert stock_of(product) == 9


def test_late_success_without_stock_is_refunded(guest_cart, product, django_capture_on_commit_callbacks):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    order = checkout(client, cart_id, payment_token="tok_3ds").data
    from apps.orders.lifecycle import expire_order

    expire_order(order["id"])
    Product.objects.filter(pk=product.pk).update(stock=0)
    SimulatedCharge.objects.filter(reference=order["payment"]["id"]).update(status=SimulatedCharge.Status.SUCCEEDED)
    with django_capture_on_commit_callbacks(execute=True):
        apply_payment_result(order["payment"]["id"], PaymentResult(PaymentStatus.SUCCEEDED, external_ref="late"))
    assert Order.objects.get(pk=order["id"]).status == "needs_attention"
    assert Payment.objects.get(order_id=order["id"]).status == "refunded"


def test_second_checkout_while_pending_returns_the_pending_order(guest_cart, product):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    first = checkout(client, cart_id, payment_token="tok_3ds").data
    second = checkout(client, cart_id, key="another-key-0002", payment_token="tok_3ds")
    assert second.status_code == 200
    assert second.data["id"] == first["id"]


def test_invoice_waits_for_clearance_before_the_buyer_sees_it(paid_flow):
    client, _, response = paid_flow
    invoice = client.get(f"/api/v1/orders/{response.data['id']}/invoice")
    assert invoice.status_code == 200
    xml = client.get(f"/api/v1/orders/{response.data['id']}/invoice?format=xml")
    assert xml["Content-Type"].startswith("application/xml")
    assert b'name="0200000"' in xml.content
    Invoice.objects.update(kind="standard", status="issued")
    pending = client.get(f"/api/v1/orders/{response.data['id']}/invoice")
    assert (pending.status_code, pending.data["code"]) == (409, "INVOICE_NOT_READY")
