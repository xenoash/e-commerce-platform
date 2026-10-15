from decimal import Decimal

import pytest
from django.db import OperationalError
from psycopg import errors as pg_errors

from apps.common.errors import problem_exception_handler
from apps.common.money import allocate, net_from_gross, to_money


def test_allocate_preserves_the_total():
    assert allocate(Decimal("10.00"), [Decimal(1)] * 3) == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]
    assert allocate(Decimal("0.05"), [Decimal(0), Decimal(0)]) == [Decimal("0.03"), Decimal("0.02")]
    assert allocate(Decimal("1.00"), []) == []


def test_money_helpers_never_use_binary_floats():
    assert to_money(0.1 + 0.2) == Decimal("0.30")
    assert net_from_gross(Decimal("115.00"), Decimal("15")) == Decimal("100.00")


@pytest.mark.parametrize(
    "cause,status,code",
    [(pg_errors.LockNotAvailable(), 409, "RESOURCE_BUSY"), (pg_errors.QueryCanceled(), 503, "TIMEOUT")],
)
def test_database_contention_maps_to_retryable_problems(cause, status, code):
    error = OperationalError("timeout")
    error.__cause__ = cause
    response = problem_exception_handler(error, {})
    assert (response.status_code, response.data["code"]) == (status, code)
    assert response["Retry-After"]


def test_unexpected_errors_are_opaque():
    response = problem_exception_handler(KeyError("secret detail"), {})
    assert response.status_code == 500
    assert "secret" not in str(response.data)


def test_request_id_is_echoed(store, client_for):
    response = client_for(store).get("/api/v1/store", HTTP_X_REQUEST_ID="trace-abc-123")
    assert response["X-Request-Id"] == "trace-abc-123"


@pytest.mark.django_db
def test_health_endpoints(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["database"] == "up"


def test_openapi_schema_is_valid(client, db):
    response = client.get("/api/v1/schema", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/carts/{cart_id}/checkout" in schema["paths"]
    parameters = schema["paths"]["/api/v1/carts/{cart_id}/checkout"]["post"]["parameters"]
    assert {"X-Store", "Idempotency-Key"} <= {p["name"] for p in parameters}


def test_store_and_payment_methods(store, client_for):
    client = client_for(store)
    assert client.get("/api/v1/store").data["prices_include_vat"] is True
    methods = {m["method"]: m for m in client.get("/api/v1/payment-methods").data}
    assert methods["card"]["requires_token"] is True
    assert methods["cod"]["requires_token"] is False


def test_sign_in(store, customer, client_for):
    client = client_for(store)
    wrong = client.post("/api/v1/auth/token", {"email": customer.email, "password": "nope"}, format="json")
    unknown = client.post("/api/v1/auth/token", {"email": "ghost@example.com", "password": "x"}, format="json")
    ok = client.post("/api/v1/auth/token", {"email": customer.email.upper(), "password": "pass-1234"}, format="json")
    assert (wrong.status_code, wrong.data["code"]) == (401, "INVALID_CREDENTIALS")
    assert unknown.status_code == 401
    assert ok.status_code == 201
    assert ok.data["token"].startswith("cst_")


def test_customer_order_history(store, customer, client_for):
    client = client_for(store, customer=customer)
    assert client.get("/api/v1/orders").data == []
    assert client_for(store).get("/api/v1/orders").status_code == 401


def test_catalogue_search_and_cursor_pagination(store, client_for):
    from conftest import ProductFactory

    for index in range(30):
        ProductFactory(name=f"Item {index:02d}", sku=f"ITEM-{index:02d}")
    client = client_for(store)
    first = client.get("/api/v1/products?limit=10").data
    second = client.get(first["next"]).data
    assert len(first["results"]) == 10
    assert first["results"][-1]["name"] < second["results"][0]["name"]
    assert client.get("/api/v1/products?q=ITEM-07").data["results"][0]["sku"] == "ITEM-07"


def test_old_idempotency_records_are_purged(store):
    from datetime import timedelta

    from django.utils import timezone

    from apps.common.models import IdempotencyRecord
    from apps.common.tasks import purge_idempotency_records

    old = IdempotencyRecord.objects.create(
        scope="checkout", resource_id="c", key="old-key-1", fingerprint="f", locked_until=timezone.now()
    )
    IdempotencyRecord.objects.create(
        scope="checkout", resource_id="c", key="new-key-1", fingerprint="f", locked_until=timezone.now()
    )
    IdempotencyRecord.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=3))
    assert purge_idempotency_records() == 1
    assert list(IdempotencyRecord.objects.values_list("key", flat=True)) == ["new-key-1"]
