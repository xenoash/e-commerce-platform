import itertools
from decimal import Decimal

import factory
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.customers.tokens import issue_token
from apps.invoicing.models import EgsDevice
from apps.invoicing.zatca.crypto import certificate_b64, generate_private_key, private_key_pem, self_signed_certificate
from apps.payments.models import StorePaymentMethod
from apps.promotions.models import Coupon
from apps.tenancy.context import reset_tenant, tenant_context
from apps.tenancy.models import Store

ADDRESS = {
    "name": "Noura Test",
    "phone": "+966500000001",
    "email": "noura@example.com",
    "street": "Test Street",
    "building_number": "1111",
    "district": "Al Olaya",
    "city": "Riyadh",
    "postal_code": "12211",
}
BILLING = {
    **ADDRESS,
    "company_name": "Test Trading Co.",
    "vat_number": "310175397400003",
    "cr_number": "1010123456",
}
_handles = itertools.count(1)


class StoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Store

    handle = factory.LazyFunction(lambda: f"store-{next(_handles)}")
    name = factory.LazyAttribute(lambda o: o.handle.title())
    legal_name = factory.LazyAttribute(lambda o: f"{o.name} Trading Company")
    vat_number = "399999999900003"
    cr_number = "1010010000"
    street = "King Fahd Road"
    building_number = "1234"
    district = "Al Olaya"
    city = "Riyadh"
    postal_code = "12211"
    shipping_fee = Decimal("25.00")
    free_shipping_threshold = Decimal("300.00")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    sku = factory.Sequence(lambda n: f"SKU-{n}")
    name = factory.Sequence(lambda n: f"Product {n}")
    price = Decimal("100.00")
    stock = 50


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    email = factory.Sequence(lambda n: f"customer{n}@example.com")
    name = "Test Customer"
    password = factory.LazyFunction(lambda: "unusable")


class CouponFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Coupon

    code = factory.Sequence(lambda n: f"CODE{n}")
    kind = Coupon.Kind.PERCENT
    value = Decimal("10")


def add_payment_methods(*methods):
    defaults = {
        "card": ("fakepay", "Card"),
        "apple_pay": ("fakepay", "Apple Pay"),
        "cod": ("cod", "Cash on delivery"),
        "net_terms": ("net_terms", "Pay on invoice"),
    }
    for method in methods:
        gateway, name = defaults[method]
        StorePaymentMethod.objects.create(method=method, gateway=gateway, display_name=name)


def add_egs_device(store):
    key = generate_private_key()
    certificate = self_signed_certificate(
        key, common_name=f"EGS-{store.handle}", organization=store.legal_name, vat_number=store.vat_number
    )
    return EgsDevice.objects.create(
        name="Test device",
        serial_number=f"1-Test|2-1.0|3-{store.pk}",
        private_key_pem=private_key_pem(key),
        certificate_b64=certificate_b64(certificate),
    )


def build_store(**overrides):
    store = StoreFactory(**overrides)
    with tenant_context(store):
        add_payment_methods("card", "apple_pay", "cod", "net_terms")
        add_egs_device(store)
    return store


@pytest.fixture(autouse=True)
def _isolated_runtime(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = False
    from config.celery import app

    app.conf.task_always_eager = True
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def store(db):
    store = build_store()
    with tenant_context(store):
        yield store
    reset_tenant()


@pytest.fixture
def other_store(db):
    return build_store()


@pytest.fixture
def product(store):
    return ProductFactory(name="Oud Royale", price=Decimal("450.00"), stock=10)


@pytest.fixture
def customer(store):
    customer = CustomerFactory(name="Sara")
    customer.set_password("pass-1234")
    customer.save()
    return customer


@pytest.fixture
def business_customer(store):
    return CustomerFactory(
        kind=Customer.Kind.BUSINESS,
        company_name="Test Trading Co.",
        vat_number="310175397400003",
        cr_number="1010123456",
        credit_approved=True,
        credit_limit=Decimal("5000.00"),
    )


class StoreClient(APIClient):
    def __init__(self, store_handle, token=None, cart_token=None, **kwargs):
        super().__init__(**kwargs)
        self.store_handle = store_handle
        self.token = token
        self.cart_token = cart_token

    def _base_environ(self, **request):
        environ = super()._base_environ(**request)
        environ.setdefault("HTTP_X_STORE", self.store_handle)
        if self.token:
            environ.setdefault("HTTP_AUTHORIZATION", f"Bearer {self.token}")
        if self.cart_token:
            environ.setdefault("HTTP_X_CART_TOKEN", self.cart_token)
        return environ


@pytest.fixture
def client_for():
    def make(store, *, customer=None, cart_token=None):
        token = None
        if customer is not None:
            with tenant_context(store):
                token, _ = issue_token(customer)
        return StoreClient(store.handle, token=token, cart_token=cart_token)

    return make


@pytest.fixture
def guest_cart(store, client_for):
    client = client_for(store)
    response = client.post("/api/v1/carts")
    client.cart_token = response.data["cart_token"]
    return client, response.data["id"]


def ready_cart(client, cart_id, product, *, quantity=1, method="card", address=None):
    client.post(f"/api/v1/carts/{cart_id}/items", {"product_id": str(product.pk), "quantity": quantity}, format="json")
    client.put(f"/api/v1/carts/{cart_id}/shipping-address", address or ADDRESS, format="json")
    response = client.put(f"/api/v1/carts/{cart_id}/payment-method", {"method": method}, format="json")
    assert response.status_code == 200, response.data
    return response.data


def checkout(client, cart_id, *, key="checkout-key-0001", **body):
    return client.post(f"/api/v1/carts/{cart_id}/checkout", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
