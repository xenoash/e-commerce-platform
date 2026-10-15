from decimal import Decimal

from apps.carts.models import Cart
from apps.carts.services import build_cart_view
from apps.catalog.models import Product, ProductRecommendation
from apps.upsell import engine
from apps.upsell.base import UpsellStrategy
from conftest import CouponFactory, ProductFactory


def cart_with(*products):
    cart = Cart.objects.create(token_hash="x" * 64)
    for product in products:
        cart.items.create(product=product, quantity=1, unit_price_seen=product.price)
    return build_cart_view(cart)


def strategies(view):
    return [(s.strategy, s.product.sku if s.product else None) for s in engine.suggest_for_cart(view)]


def test_default_pipeline_mixes_strategies(store):
    oud = ProductFactory(sku="OUD", price=Decimal("120.00"))
    bakhoor = ProductFactory(sku="BKH", price=Decimal("60.00"))
    ProductFactory(sku="BIG", price=Decimal("200.00"))
    ProductRecommendation.objects.create(product=oud, recommended=bakhoor)
    CouponFactory(code="SAVE50", advertise=True, rules=[{"type": "min_subtotal", "amount": "400"}])
    suggestions = strategies(cart_with(oud))
    assert ("related_products", "BKH") in suggestions
    assert ("free_shipping_gap", None) in suggestions
    assert ("free_shipping_gap", "BIG") in suggestions
    assert ("coupon_unlock", None) in suggestions


def test_suggestions_skip_items_in_cart_and_sold_out_products(store):
    oud = ProductFactory(sku="OUD")
    sold_out = ProductFactory(sku="GONE", stock=0)
    in_cart = ProductFactory(sku="HAVE")
    ProductRecommendation.objects.create(product=oud, recommended=sold_out)
    ProductRecommendation.objects.create(product=oud, recommended=in_cart)
    skus = {sku for _, sku in strategies(cart_with(oud, in_cart))}
    assert not {"GONE", "HAVE", "OUD"} & skus


def test_private_coupons_are_never_advertised(store):
    CouponFactory(code="SECRET", advertise=False, rules=[{"type": "min_subtotal", "amount": "999"}])
    assert all(s.data.get("coupon_code") != "SECRET" for s in engine.suggest_for_cart(cart_with(ProductFactory())))


class ExplodingStrategy(UpsellStrategy):
    key = "exploding"

    def suggest(self, view, config):
        raise RuntimeError("recommendation service is down")


def test_a_failing_strategy_never_breaks_the_cart(store, settings):
    settings.UPSELL_STRATEGIES = {
        **settings.UPSELL_STRATEGIES,
        "exploding": "apps.upsell.tests.test_engine.ExplodingStrategy",
    }
    engine.strategy.cache_clear()
    store.upsell_config = [{"strategy": "exploding"}, {"strategy": "free_shipping_gap"}]
    suggestions = engine.suggest_for_cart(cart_with(ProductFactory(price=Decimal("50.00"))))
    assert [s.strategy for s in suggestions][:1] == ["free_shipping_gap"]


def test_service_addons_offer_gift_wrapping_for_physical_goods(store):
    ProductFactory(sku="WRAP", kind=Product.Kind.SERVICE, is_addon=True, track_stock=False, price=Decimal("15.00"))
    store.upsell_config = [{"strategy": "service_addons"}]
    assert strategies(cart_with(ProductFactory())) == [("service_addons", "WRAP")]


def test_suggestions_endpoint(guest_cart, product):
    client, cart_id = guest_cart
    client.post(f"/api/v1/carts/{cart_id}/items", {"product_id": str(product.pk)}, format="json")
    response = client.get(f"/api/v1/carts/{cart_id}/suggestions")
    assert response.status_code == 200
    for suggestion in response.data["suggestions"]:
        assert suggestion["type"] in ("product", "message")
        if suggestion["product"]:
            assert suggestion["action"]["product_id"] == suggestion["product"]["id"]
