import pytest
from django.apps import apps
from django.db import IntegrityError, ProgrammingError, connection, transaction

from apps.catalog.models import Product
from apps.tenancy.context import CrossTenantWrite, TenantNotSet, reset_tenant, rls_bypass, tenant_context
from apps.tenancy.models import TenantModel
from conftest import ProductFactory, ready_cart


def tenant_tables():
    return sorted(
        model._meta.db_table
        for model in apps.get_models()
        if issubclass(model, TenantModel) and not model._meta.abstract
    )


def count_rows(table, row_id):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM {table} WHERE id = %s", [row_id])
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_app_role_is_subject_to_row_level_security():
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        assert cursor.fetchone() == (False, False)


@pytest.mark.django_db
def test_every_tenant_table_forces_row_level_security():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_policies p ON p.tablename = c.relname "
            "WHERE c.relrowsecurity AND c.relforcerowsecurity AND p.policyname = 'tenant_isolation'"
        )
        protected = {row[0] for row in cursor.fetchall()}
    assert set(tenant_tables()) <= protected, set(tenant_tables()) - protected


@pytest.mark.django_db
def test_manager_fails_closed_without_an_active_store():
    reset_tenant()
    with pytest.raises(TenantNotSet):
        list(Product.objects.all())


def test_rls_hides_other_store_rows_even_from_raw_sql(store, other_store):
    product = ProductFactory()
    assert count_rows("catalog_product", product.pk) == 1
    with tenant_context(other_store):
        assert count_rows("catalog_product", product.pk) == 0
        assert Product.unscoped.filter(pk=product.pk).count() == 0
    reset_tenant()
    assert count_rows("catalog_product", product.pk) == 0


def test_rls_blocks_writing_rows_for_another_store(store, other_store):
    with pytest.raises(ProgrammingError, match="row-level security"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO catalog_product (id, store_id, sku, name, description, kind, price, track_stock, stock, "
                "max_per_order, is_addon, is_active, image_url, created_at, updated_at) VALUES (gen_random_uuid(), "
                "%s, 'X', 'X', '', 'physical', 1, true, 1, 1, false, true, '', now(), now())",
                [other_store.pk],
            )


def test_save_refuses_an_instance_from_another_store(store, other_store):
    product = ProductFactory()
    with tenant_context(other_store), pytest.raises(CrossTenantWrite):
        product.save()


def test_rls_bypass_does_not_outlive_its_block(store, other_store):
    with tenant_context(other_store):
        ProductFactory()
    with rls_bypass():
        assert Product.objects.count() == 1
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.rls_bypass', true)")
        assert cursor.fetchone()[0] in (None, "", "off")
    assert Product.objects.count() == 0


def test_unique_constraints_are_scoped_per_store(store, other_store):
    ProductFactory(sku="SAME")
    with tenant_context(other_store):
        ProductFactory(sku="SAME")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(sku="SAME")


@pytest.mark.django_db
def test_requests_must_name_a_known_store(client_for, store):
    from rest_framework.test import APIClient

    missing = APIClient().get("/api/v1/products")
    unknown = APIClient().get("/api/v1/products", HTTP_X_STORE="no-such-store")
    assert (missing.status_code, missing.json()["code"]) == (400, "STORE_HEADER_MISSING")
    assert (unknown.status_code, unknown.json()["code"]) == (404, "STORE_NOT_FOUND")


def test_customer_token_is_rejected_by_another_store(store, other_store, customer, client_for):
    own = client_for(store, customer=customer)
    foreign = client_for(other_store)
    foreign.token = own.token
    assert own.get("/api/v1/me").status_code == 200
    response = foreign.get("/api/v1/me")
    assert (response.status_code, response.json()["code"]) == (401, "INVALID_TOKEN")


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/carts/{cart}"),
        ("post", "/api/v1/carts/{cart}/items"),
        ("put", "/api/v1/carts/{cart}/coupon"),
        ("delete", "/api/v1/carts/{cart}/coupon"),
        ("put", "/api/v1/carts/{cart}/payment-method"),
        ("get", "/api/v1/carts/{cart}/suggestions"),
        ("post", "/api/v1/carts/{cart}/checkout"),
        ("get", "/api/v1/orders/{order}"),
        ("post", "/api/v1/orders/{order}/payment/confirm"),
        ("get", "/api/v1/orders/{order}/invoice"),
        ("get", "/api/v1/products/{product}"),
    ],
)
def test_every_resource_is_invisible_from_another_store(
    method, path, store, other_store, product, guest_cart, client_for
):
    client, cart_id = guest_cart
    ready_cart(client, cart_id, product)
    order = client.post(
        f"/api/v1/carts/{cart_id}/checkout",
        {"payment_token": "tok_3ds"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="isolation-key-1",
    ).json()
    intruder = client_for(other_store, cart_token=client.cart_token)
    url = path.format(cart=cart_id, order=order["id"], product=product.pk)
    body = {"product_id": str(product.pk), "quantity": 1, "code": "ANY", "method": "card"}
    response = getattr(intruder, method)(url, body, format="json", HTTP_IDEMPOTENCY_KEY="isolation-key-2")
    assert response.status_code == 404, response.json()
