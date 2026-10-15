from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from apps.carts.pricing import DiscountSpec, PricingLine, PricingPolicy, price_cart
from apps.common.money import vat_for_net

INCLUSIVE = PricingPolicy(prices_include_vat=True, vat_rate=Decimal("15.00"), shipping_fee=Decimal("25.00"))
EXCLUSIVE = PricingPolicy(prices_include_vat=False, vat_rate=Decimal("15.00"), shipping_fee=Decimal("40.00"))


def line(key, price, quantity=1, shipped=True, product=None):
    return PricingLine(
        key=key, product_id=product or key, quantity=quantity, unit_price=Decimal(price), requires_shipping=shipped
    )


def test_vat_inclusive_prices_split_into_net_and_vat():
    priced = price_cart([line("a", "115.00")], INCLUSIVE)
    assert priced.total == Decimal("140.00")
    assert priced.taxable_amount == Decimal("121.74")
    assert priced.vat == Decimal("18.26")
    assert priced.line("a").net + priced.line("a").vat == Decimal("115.00")


def test_vat_exclusive_prices_add_vat_on_top():
    priced = price_cart([line("a", "100.00", 3)], EXCLUSIVE)
    assert priced.taxable_amount == Decimal("340.00")
    assert priced.vat == Decimal("51.00")
    assert priced.total == Decimal("391.00")


def test_percent_discount_is_capped_and_spread_over_lines():
    spec = DiscountSpec(kind="percent", value=Decimal("15"), max_discount=Decimal("50.00"))
    priced = price_cart([line("a", "300.00"), line("b", "100.00")], INCLUSIVE, spec)
    assert priced.item_discount == Decimal("50.00")
    assert priced.line("a").discount + priced.line("b").discount == Decimal("50.00")
    assert priced.line("a").discount == Decimal("37.50")


def test_fixed_discount_never_exceeds_eligible_items():
    spec = DiscountSpec(kind="fixed", value=Decimal("80.00"), eligible_product_ids=frozenset({"b"}))
    priced = price_cart([line("a", "300.00"), line("b", "50.00")], INCLUSIVE, spec)
    assert priced.item_discount == Decimal("50.00")
    assert priced.line("a").discount == Decimal("0.00")


def test_free_shipping_threshold_uses_discounted_merchandise():
    policy = PricingPolicy(True, Decimal("15.00"), Decimal("25.00"), free_shipping_threshold=Decimal("300.00"))
    above = price_cart([line("a", "300.00")], policy)
    below = price_cart([line("a", "300.00")], policy, DiscountSpec(kind="fixed", value=Decimal("10.00")))
    assert above.shipping_fee == Decimal("0.00")
    assert below.shipping_fee == Decimal("25.00")


def test_free_shipping_coupon_discounts_only_the_fee():
    priced = price_cart([line("a", "100.00")], INCLUSIVE, DiscountSpec(kind="free_shipping", value=Decimal(0)))
    assert priced.shipping_discount == Decimal("25.00")
    assert priced.total == Decimal("100.00")


def test_services_alone_do_not_pay_shipping():
    priced = price_cart([line("a", "15.00", shipped=False)], INCLUSIVE)
    assert priced.shipping_fee == Decimal("0.00")


prices = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("5000.00"), places=2)
lines_strategy = st.lists(
    st.tuples(prices, st.integers(min_value=1, max_value=20), st.booleans()), min_size=1, max_size=6
)
discounts = st.one_of(
    st.none(),
    st.builds(lambda v: DiscountSpec("percent", v), st.decimals(min_value=1, max_value=100, places=0)),
    st.builds(lambda v: DiscountSpec("fixed", v), prices),
    st.just(DiscountSpec("free_shipping", Decimal(0))),
)


@settings(max_examples=300, deadline=None)
@given(lines_strategy, discounts, st.booleans())
def test_totals_always_satisfy_zatca_arithmetic(raw_lines, discount, inclusive):
    policy = INCLUSIVE if inclusive else EXCLUSIVE
    cart_lines = [line(str(i), price, quantity, shipped) for i, (price, quantity, shipped) in enumerate(raw_lines)]
    priced = price_cart(cart_lines, policy, discount)
    components = [*priced.lines, priced.shipping]

    assert sum(c.net for c in components) == priced.taxable_amount
    assert sum(c.vat for c in components) == priced.vat
    assert priced.total == priced.taxable_amount + priced.vat
    assert all(c.total == c.net + c.vat for c in components)
    assert all(c.net >= 0 and c.vat >= 0 for c in components)
    assert abs(priced.vat - vat_for_net(priced.taxable_amount, policy.vat_rate)) <= Decimal("0.01")
    assert priced.item_discount <= priced.eligible_subtotal
    charged = priced.subtotal - priced.discount + priced.shipping_fee
    assert priced.total == (charged if inclusive else charged + priced.vat)
