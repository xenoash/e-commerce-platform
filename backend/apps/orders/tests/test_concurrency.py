import threading
from collections import Counter

import pytest
from django.db import connection

from apps.carts.models import CartItem
from apps.catalog.models import Product
from apps.orders.models import Order
from apps.promotions.models import Coupon
from conftest import CouponFactory, ProductFactory, ready_cart

pytestmark = pytest.mark.django_db(transaction=True)


def run_concurrently(count, task):
    barrier = threading.Barrier(count)
    results = [None] * count
    errors = []

    def worker(index):
        try:
            barrier.wait(timeout=10)
            results[index] = task(index)
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors
    return results


def open_carts(store, client_for, count, product, **cart_kwargs):
    carts = []
    for _ in range(count):
        client = client_for(store)
        created = client.post("/api/v1/carts").data
        client.cart_token = created["cart_token"]
        ready_cart(client, created["id"], product, **cart_kwargs)
        carts.append((client, created["id"]))
    return carts


def checkout_call(client, cart_id, key, token="tok_success"):
    response = client.post(
        f"/api/v1/carts/{cart_id}/checkout", {"payment_token": token}, format="json", HTTP_IDEMPOTENCY_KEY=key
    )
    return response.status_code, response.json()


def test_last_unit_is_sold_exactly_once(store, client_for):
    product = ProductFactory(stock=1)
    carts = open_carts(store, client_for, 6, product)
    results = run_concurrently(6, lambda i: checkout_call(*carts[i], key=f"last-unit-{i:04d}"))
    statuses = Counter((status, body.get("code") or body.get("status")) for status, body in results)
    assert statuses == {(201, "paid"): 1, (409, "OUT_OF_STOCK"): 5}
    assert Product.objects.get(pk=product.pk).stock == 0
    assert Order.objects.filter(status="paid").count() == 1


def test_single_use_coupon_is_redeemed_once(store, client_for):
    product = ProductFactory(stock=100)
    CouponFactory(code="ONLYONE", usage_limit=1)
    carts = open_carts(store, client_for, 5, product)
    for client, cart_id in carts:
        assert client.put(f"/api/v1/carts/{cart_id}/coupon", {"code": "ONLYONE"}, format="json").status_code == 200
    results = run_concurrently(5, lambda i: checkout_call(*carts[i], key=f"coupon-race-{i:04d}"))
    outcomes = Counter(
        (body.get("code"), body.get("reason")) if status == 409 else body["status"] for status, body in results
    )
    assert outcomes == {"paid": 1, ("COUPON_NOT_APPLICABLE", "COUPON_USAGE_LIMIT_REACHED"): 4}
    assert Coupon.objects.get(code="ONLYONE").times_used == 1
    assert Product.objects.get(pk=product.pk).stock == 99


def test_same_idempotency_key_never_creates_two_orders(store, client_for):
    product = ProductFactory(stock=100)
    [(client, cart_id)] = open_carts(store, client_for, 1, product)
    results = run_concurrently(6, lambda i: checkout_call(client, cart_id, key="one-key-for-all"))
    order_ids = {body["id"] for status, body in results if status in (200, 201)}
    in_progress = [body for status, body in results if status == 409]
    assert len(order_ids) == 1
    assert all(body["code"] == "REQUEST_IN_PROGRESS" for body in in_progress)
    assert Order.objects.count() == 1
    assert Product.objects.get(pk=product.pk).stock == 99


def test_double_click_with_fresh_keys_still_places_one_order(store, client_for):
    product = ProductFactory(stock=100)
    [(client, cart_id)] = open_carts(store, client_for, 1, product)
    results = run_concurrently(5, lambda i: checkout_call(client, cart_id, key=f"click-{i:04d}", token="tok_3ds"))
    assert Order.objects.count() == 1
    assert {status for status, _ in results} <= {200, 201}
    assert len({body["id"] for _, body in results}) == 1


def test_concurrent_adds_are_never_lost(store, client_for):
    product = ProductFactory(stock=100, max_per_order=50)
    client = client_for(store)
    created = client.post("/api/v1/carts").data
    client.cart_token = created["cart_token"]
    url = f"/api/v1/carts/{created['id']}/items"
    run_concurrently(8, lambda i: client.post(url, {"product_id": str(product.pk), "quantity": 1}, format="json"))
    item = CartItem.objects.get(cart_id=created["id"])
    assert item.quantity == 8
    assert item.cart.version == 9
