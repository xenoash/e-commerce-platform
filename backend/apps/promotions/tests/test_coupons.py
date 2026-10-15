from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.promotions.rules import InvalidRuleConfig, build_rules
from apps.promotions.services import evaluate_coupon
from conftest import CouponFactory, CustomerFactory


def evaluate(coupon, *, subtotal="500.00", products=("p1",), customer=None, city="Riyadh"):
    return evaluate_coupon(
        coupon, subtotal=Decimal(subtotal), product_ids=products, customer=customer, shipping_city=city
    )


def code_of(evaluation):
    return None if evaluation.applicable else str(evaluation.problem.code)


def test_min_subtotal_reports_how_much_is_missing(store):
    coupon = CouponFactory(rules=[{"type": "min_subtotal", "amount": "400"}])
    result = evaluate(coupon, subtotal="250.00")
    assert code_of(result) == "COUPON_MIN_SUBTOTAL_NOT_MET"
    assert result.problem.extra == {"required": "400.00", "current": "250.00", "remaining": "150.00"}
    assert evaluate(coupon, subtotal="400.00").applicable


def test_city_rule_needs_an_address_and_a_matching_city(store):
    coupon = CouponFactory(rules=[{"type": "allowed_cities", "cities": ["Riyadh", "Jeddah"]}])
    assert code_of(evaluate(coupon, city=None)) == "COUPON_REQUIRES_SHIPPING_ADDRESS"
    assert code_of(evaluate(coupon, city="Dammam")) == "COUPON_CITY_NOT_ELIGIBLE"
    assert evaluate(coupon, city="jeddah").applicable


def test_customer_kind_rule(store):
    coupon = CouponFactory(rules=[{"type": "customer_kind", "kinds": ["business"]}])
    business = CustomerFactory(kind="business")
    assert code_of(evaluate(coupon)) == "COUPON_CUSTOMER_KIND_NOT_ELIGIBLE"
    assert evaluate(coupon, customer=business).applicable


def test_first_order_only(store, customer, monkeypatch):
    coupon = CouponFactory(rules=[{"type": "first_order_only"}])
    assert code_of(evaluate(coupon)) == "COUPON_REQUIRES_CUSTOMER"
    assert evaluate(coupon, customer=customer).applicable
    monkeypatch.setattr("apps.promotions.services.customer_has_prior_orders", lambda c: True)
    assert code_of(evaluate(coupon, customer=customer)) == "COUPON_FIRST_ORDER_ONLY"


@pytest.mark.parametrize(
    "fields,code",
    [
        ({"is_active": False}, "COUPON_NOT_ACTIVE"),
        ({"starts_at": timezone.now() + timedelta(days=1)}, "COUPON_NOT_STARTED"),
        ({"ends_at": timezone.now() - timedelta(seconds=1)}, "COUPON_EXPIRED"),
        ({"usage_limit": 3, "times_used": 3}, "COUPON_USAGE_LIMIT_REACHED"),
        ({"per_customer_limit": 1}, "COUPON_REQUIRES_CUSTOMER"),
        ({"applies_to_product_ids": ["other"]}, "COUPON_NO_ELIGIBLE_ITEMS"),
    ],
)
def test_lifecycle_and_limit_checks(store, fields, code):
    assert code_of(evaluate(CouponFactory(**fields))) == code


def test_unknown_or_malformed_rules_are_rejected():
    with pytest.raises(InvalidRuleConfig):
        build_rules([{"type": "no_such_rule"}])
    with pytest.raises(InvalidRuleConfig):
        build_rules([{"type": "min_subtotal"}])
    with pytest.raises(InvalidRuleConfig):
        build_rules([{"type": "customer_kind", "kinds": ["robots"]}])


def test_unknown_code_is_a_422(guest_cart):
    client, cart_id = guest_cart
    response = client.put(f"/api/v1/carts/{cart_id}/coupon", {"code": "NOPE"}, format="json")
    assert (response.status_code, response.data["code"]) == (422, "COUPON_NOT_FOUND")
