from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from apps.common.errors import ErrorCode, Problem
from apps.common.money import format_amount, to_money


@dataclass(frozen=True)
class RuleContext:
    subtotal: Decimal
    product_ids: frozenset[str]
    customer_kind: str
    customer_id: str | None
    shipping_city: str | None
    has_prior_orders: Callable[[], bool] = field(default=lambda: False)


class InvalidRuleConfig(ValueError):
    pass


class CouponRule(ABC):
    type: ClassVar[str]

    @classmethod
    @abstractmethod
    def from_config(cls, config: dict) -> CouponRule: ...

    @abstractmethod
    def check(self, context: RuleContext) -> Problem | None: ...


RULES: dict[str, type[CouponRule]] = {}


def register(rule_class):
    RULES[rule_class.type] = rule_class
    return rule_class


def build_rules(raw_rules):
    if not isinstance(raw_rules, list):
        raise InvalidRuleConfig("Coupon rules must be a list.")
    rules = []
    for raw in raw_rules:
        if not isinstance(raw, dict) or raw.get("type") not in RULES:
            raise InvalidRuleConfig(f"Unknown coupon rule: {raw!r}")
        rules.append(RULES[raw["type"]].from_config(raw))
    return rules


@register
@dataclass(frozen=True)
class MinSubtotal(CouponRule):
    type: ClassVar[str] = "min_subtotal"
    amount: Decimal

    @classmethod
    def from_config(cls, config):
        try:
            amount = to_money(config["amount"])
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise InvalidRuleConfig("min_subtotal needs a decimal 'amount'.") from exc
        return cls(amount=amount)

    def check(self, context):
        if context.subtotal >= self.amount:
            return None
        remaining = self.amount - context.subtotal
        return Problem(
            422,
            ErrorCode.COUPON_MIN_SUBTOTAL_NOT_MET,
            f"Add {format_amount(remaining)} more to use this coupon.",
            required=format_amount(self.amount),
            current=format_amount(context.subtotal),
            remaining=format_amount(remaining),
        )


@register
@dataclass(frozen=True)
class AllowedCities(CouponRule):
    type: ClassVar[str] = "allowed_cities"
    cities: frozenset[str]
    display: tuple[str, ...]

    @classmethod
    def from_config(cls, config):
        cities = config.get("cities")
        if not cities or not all(isinstance(city, str) for city in cities):
            raise InvalidRuleConfig("allowed_cities needs a non-empty 'cities' list.")
        return cls(cities=frozenset(city.casefold() for city in cities), display=tuple(cities))

    def check(self, context):
        if not context.shipping_city:
            return Problem(
                422,
                ErrorCode.COUPON_REQUIRES_SHIPPING_ADDRESS,
                "Add a shipping address to check this coupon.",
                allowed_cities=list(self.display),
            )
        if context.shipping_city.casefold() not in self.cities:
            return Problem(
                422,
                ErrorCode.COUPON_CITY_NOT_ELIGIBLE,
                f"This coupon is only valid for deliveries to {', '.join(self.display)}.",
                allowed_cities=list(self.display),
                city=context.shipping_city,
            )
        return None


@register
@dataclass(frozen=True)
class CustomerKind(CouponRule):
    type: ClassVar[str] = "customer_kind"
    kinds: frozenset[str]

    @classmethod
    def from_config(cls, config):
        kinds = frozenset(config.get("kinds") or [])
        if not kinds or not kinds <= {"individual", "business"}:
            raise InvalidRuleConfig("customer_kind needs 'kinds' from individual and business.")
        return cls(kinds=kinds)

    def check(self, context):
        if context.customer_kind in self.kinds:
            return None
        return Problem(
            422,
            ErrorCode.COUPON_CUSTOMER_KIND_NOT_ELIGIBLE,
            "This coupon is not available for this type of account.",
            allowed_kinds=sorted(self.kinds),
        )


@register
@dataclass(frozen=True)
class FirstOrderOnly(CouponRule):
    type: ClassVar[str] = "first_order_only"

    @classmethod
    def from_config(cls, config):
        return cls()

    def check(self, context):
        if context.customer_id is None:
            return Problem(422, ErrorCode.COUPON_REQUIRES_CUSTOMER, "Sign in to use this first-order coupon.")
        if context.has_prior_orders():
            return Problem(422, ErrorCode.COUPON_FIRST_ORDER_ONLY, "This coupon is only valid on a first order.")
        return None
