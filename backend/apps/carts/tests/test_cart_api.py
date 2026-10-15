from decimal import Decimal

import pytest

from apps.carts.models import Cart
from conftest import ADDRESS, BILLING, CouponFactory, ProductFactory, ready_cart


def items_url(cart_id):
    return f"/api/v1/carts/{cart_id}/items"


def test_guest_cart_needs_its_token(store, client_for):
    client = client_for(store)
    created = client.post("/api/v1/carts")
    assert created.status_code == 201
    assert created.data["cart_token"].startswith("ctk_")
    assert created["ETag"] == '"1"'
    assert client.get(f"/api/v1/carts/{created.data['id']}").status_code == 404
    client.cart_token = created.data["cart_token"]
    assert client.get(f"/api/v1/carts/{created.data['id']}").status_code == 200


def test_signed_in_customer_gets_the_same_active_cart(store, customer, client_for):
    client = client_for(store, customer=customer)
    first = client.post("/api/v1/carts")
    second = client.post("/api/v1/carts")
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.data["id"] == second.data["id"]
    assert first.data["cart_token"] is None


def test_adding_the_same_product_merges_lines(guest_cart, product):
    client, cart_id = guest_cart
    client.post(items_url(cart_id), {"product_id": str(product.pk), "quantity": 1}, format="json")
    response = client.post(items_url(cart_id), {"product_id": str(product.pk), "quantity": 2}, format="json")
    assert response.status_code == 200
    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["quantity"] == 3
    assert response.data["version"] == 3


def test_quantity_and_stock_limits(guest_cart, store):
    client, cart_id = guest_cart
    scarce = ProductFactory(stock=2, max_per_order=5)
    over_stock = client.post(items_url(cart_id), {"product_id": str(scarce.pk), "quantity": 3}, format="json")
    over_limit = client.post(items_url(cart_id), {"product_id": str(scarce.pk), "quantity": 6}, format="json")
    unknown = client.post(
        items_url(cart_id), {"product_id": "01a13e75-0000-7000-8000-000000000000", "quantity": 1}, format="json"
    )
    assert (over_stock.status_code, over_stock.data["code"]) == (409, "OUT_OF_STOCK")
    assert over_stock.data["items"][0]["available"] == 2
    assert (over_limit.status_code, over_limit.data["code"]) == (422, "QUANTITY_LIMIT_EXCEEDED")
    assert (unknown.status_code, unknown.data["code"]) == (422, "PRODUCT_NOT_FOUND")


def test_validation_errors_list_every_field(guest_cart):
    client, cart_id = guest_cart
    response = client.put(f"/api/v1/carts/{cart_id}/shipping-address", {"name": "x", "postal_code": "1"}, format="json")
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    fields = {error["field"] for error in response.data["errors"]}
    assert {"phone", "street", "postal_code", "building_number"} <= fields


def test_update_and_remove_items(guest_cart, product):
    client, cart_id = guest_cart
    item_id = client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json").data["items"][0]["id"]
    updated = client.patch(f"{items_url(cart_id)}/{item_id}", {"quantity": 4}, format="json")
    assert updated.data["items"][0]["quantity"] == 4
    removed = client.delete(f"{items_url(cart_id)}/{item_id}")
    assert removed.data["items"] == []
    missing = client.delete(f"{items_url(cart_id)}/{item_id}")
    assert (missing.status_code, missing.data["code"]) == (404, "CART_ITEM_NOT_FOUND")


def test_stale_if_match_is_rejected(guest_cart, product):
    client, cart_id = guest_cart
    client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json")
    stale = client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json", HTTP_IF_MATCH='"1"')
    fresh = client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json", HTTP_IF_MATCH='"2"')
    assert (stale.status_code, stale.data["code"], stale.data["current_version"]) == (412, "CART_VERSION_MISMATCH", 2)
    assert fresh.status_code == 200


def test_readiness_lists_what_is_missing(guest_cart, product):
    client, cart_id = guest_cart
    empty = client.get(f"/api/v1/carts/{cart_id}").data["checkout_readiness"]
    assert empty == {"ready": False, "missing": ["items", "payment_method"]}
    ready = ready_cart(client, cart_id, product)
    assert ready["checkout_readiness"] == {"ready": True, "missing": []}


def test_price_change_is_flagged_and_used(guest_cart, product):
    client, cart_id = guest_cart
    client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json")
    product.price = Decimal("500.00")
    product.save()
    cart = client.get(f"/api/v1/carts/{cart_id}").data
    assert cart["items"][0]["unit_price"] == "500.00"
    assert cart["warnings"][0]["code"] == "PRICE_CHANGED"
    assert cart["warnings"][0]["previous_price"] == "450.00"


def test_unavailable_item_blocks_checkout(guest_cart, product):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product, quantity=2)
    product.stock = 1
    product.save()
    cart = client.get(f"/api/v1/carts/{cart_id}").data
    assert "available_items" in cart["checkout_readiness"]["missing"]
    assert cart["items"][0]["available"] is False


def test_coupon_apply_and_remove(guest_cart, product):
    client, cart_id = guest_cart
    CouponFactory(code="TEN", value=Decimal("10"))
    client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json")
    applied = client.put(f"/api/v1/carts/{cart_id}/coupon", {"code": "ten"}, format="json")
    assert applied.data["coupon"]["applicable"] is True
    assert applied.data["totals"]["discount"] == "45.00"
    removed = client.delete(f"/api/v1/carts/{cart_id}/coupon")
    again = client.delete(f"/api/v1/carts/{cart_id}/coupon")
    assert removed.data["coupon"] is None
    assert again.status_code == 200


def test_coupon_that_stops_applying_stays_visible(guest_cart, product):
    client, cart_id = guest_cart
    CouponFactory(code="RIYADH", rules=[{"type": "allowed_cities", "cities": ["Riyadh"]}])
    client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json")
    client.put(f"/api/v1/carts/{cart_id}/shipping-address", ADDRESS, format="json")
    client.put(f"/api/v1/carts/{cart_id}/coupon", {"code": "RIYADH"}, format="json")
    moved = client.put(f"/api/v1/carts/{cart_id}/shipping-address", {**ADDRESS, "city": "Jeddah"}, format="json")
    assert moved.data["coupon"]["applicable"] is False
    assert moved.data["coupon"]["reason"]["code"] == "COUPON_CITY_NOT_ELIGIBLE"
    assert moved.data["totals"]["discount"] == "0.00"
    assert "applicable_coupon" in moved.data["checkout_readiness"]["missing"]


def test_net_terms_is_only_for_approved_businesses(store, guest_cart, business_customer, client_for):
    client, cart_id = guest_cart
    refused = client.put(f"/api/v1/carts/{cart_id}/payment-method", {"method": "net_terms"}, format="json")
    assert (refused.status_code, refused.data["code"]) == (422, "PAYMENT_METHOD_NOT_ALLOWED")
    business = client_for(store, customer=business_customer)
    business_cart = business.post("/api/v1/carts").data["id"]
    accepted = business.put(f"/api/v1/carts/{business_cart}/payment-method", {"method": "net_terms"}, format="json")
    assert accepted.status_code == 200


def test_business_cart_needs_billing_for_a_standard_invoice(store, business_customer, client_for, product):
    client = client_for(store, customer=business_customer)
    cart_id = client.post("/api/v1/carts").data["id"]
    cart = ready_cart(client, cart_id, product, method="net_terms")
    assert cart["invoice_kind"] == "standard"
    assert cart["checkout_readiness"]["missing"] == ["billing_address"]
    billed = client.put(f"/api/v1/carts/{cart_id}/billing-address", BILLING, format="json")
    assert billed.data["checkout_readiness"]["ready"] is True


def test_billing_vat_number_requires_company_name(guest_cart):
    client, cart_id = guest_cart
    response = client.put(f"/api/v1/carts/{cart_id}/billing-address", {**BILLING, "company_name": ""}, format="json")
    assert response.status_code == 400
    assert response.data["errors"][0]["field"] == "company_name"


@pytest.mark.parametrize("status", [Cart.Status.CONVERTED, Cart.Status.CHECKING_OUT])
def test_closed_carts_cannot_change(guest_cart, product, status):
    client, cart_id = guest_cart
    Cart.objects.filter(pk=cart_id).update(status=status)
    response = client.post(items_url(cart_id), {"product_id": str(product.pk)}, format="json")
    assert (response.status_code, response.data["code"]) == (409, "CART_NOT_OPEN")
