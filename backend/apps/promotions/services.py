from dataclasses import dataclass

from django.db.models import F, Q
from django.utils import timezone

from apps.carts.pricing import DiscountSpec
from apps.common.errors import ErrorCode, Problem

from .models import Coupon, CouponRedemption
from .rules import RuleContext, build_rules


@dataclass(frozen=True)
class CouponEvaluation:
    coupon: Coupon
    problem: Problem | None

    @property
    def applicable(self):
        return self.problem is None

    def discount_spec(self):
        if not self.applicable:
            return None
        eligible = frozenset(str(pid) for pid in self.coupon.applies_to_product_ids) or None
        return DiscountSpec(
            kind=self.coupon.kind,
            value=self.coupon.value,
            max_discount=self.coupon.max_discount,
            eligible_product_ids=eligible,
        )


def find_coupon(code):
    coupon = Coupon.objects.filter(code__iexact=(code or "").strip()).first()
    if coupon is None:
        raise Problem(422, ErrorCode.COUPON_NOT_FOUND, "This coupon code does not exist.")
    return coupon


def customer_has_prior_orders(customer):
    from apps.orders.models import Order

    return Order.objects.filter(customer=customer, status__in=Order.FULFILLABLE_STATUSES).exists()


def active_redemptions(coupon, customer):
    return CouponRedemption.objects.filter(coupon=coupon, customer=customer, released_at__isnull=True).count()


def evaluate_coupon(coupon, *, subtotal, product_ids, customer, shipping_city, now=None):
    now = now or timezone.now()
    product_ids = frozenset(str(pid) for pid in product_ids)

    def fail(code, detail, **extra):
        return CouponEvaluation(coupon, Problem(422, code, detail, **extra))

    if not coupon.is_active:
        return fail(ErrorCode.COUPON_NOT_ACTIVE, "This coupon is no longer active.")
    if coupon.starts_at and now < coupon.starts_at:
        return fail(
            ErrorCode.COUPON_NOT_STARTED, "This coupon is not valid yet.", starts_at=coupon.starts_at.isoformat()
        )
    if coupon.ends_at and now >= coupon.ends_at:
        return fail(ErrorCode.COUPON_EXPIRED, "This coupon has expired.", ended_at=coupon.ends_at.isoformat())
    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        return fail(ErrorCode.COUPON_USAGE_LIMIT_REACHED, "This coupon has been fully redeemed.")
    if coupon.per_customer_limit is not None:
        if customer is None:
            return fail(ErrorCode.COUPON_REQUIRES_CUSTOMER, "Sign in to use this coupon.")
        if active_redemptions(coupon, customer) >= coupon.per_customer_limit:
            return fail(ErrorCode.COUPON_CUSTOMER_LIMIT_REACHED, "You have already used this coupon.")
    eligible = frozenset(str(pid) for pid in coupon.applies_to_product_ids)
    if eligible and not eligible & product_ids:
        return fail(ErrorCode.COUPON_NO_ELIGIBLE_ITEMS, "None of the items in the cart qualify for this coupon.")

    context = RuleContext(
        subtotal=subtotal,
        product_ids=product_ids,
        customer_kind=customer.kind if customer is not None else "individual",
        customer_id=str(customer.pk) if customer is not None else None,
        shipping_city=shipping_city,
        has_prior_orders=lambda: customer is not None and customer_has_prior_orders(customer),
    )
    for rule in build_rules(coupon.rules):
        problem = rule.check(context)
        if problem is not None:
            return CouponEvaluation(coupon, problem)
    return CouponEvaluation(coupon, None)


def redeem_coupon(coupon, *, order, customer, amount):
    claimed = (
        Coupon.objects.filter(pk=coupon.pk, is_active=True)
        .filter(Q(usage_limit__isnull=True) | Q(times_used__lt=F("usage_limit")))
        .update(times_used=F("times_used") + 1)
    )
    if not claimed:
        raise Problem(409, ErrorCode.COUPON_USAGE_LIMIT_REACHED, "This coupon was fully redeemed a moment ago.")
    if coupon.per_customer_limit is not None and active_redemptions(coupon, customer) >= coupon.per_customer_limit:
        raise Problem(409, ErrorCode.COUPON_CUSTOMER_LIMIT_REACHED, "You have already used this coupon.")
    return CouponRedemption.objects.create(coupon=coupon, order=order, customer=customer, amount=amount)


def release_coupon(order):
    redemption = CouponRedemption.objects.filter(order=order, released_at__isnull=True).first()
    if redemption is None:
        return False
    released = CouponRedemption.objects.filter(pk=redemption.pk, released_at__isnull=True).update(
        released_at=timezone.now()
    )
    if released:
        Coupon.objects.filter(pk=redemption.coupon_id, times_used__gt=0).update(times_used=F("times_used") - 1)
    return bool(released)


def reclaim_coupon(order):
    redemption = CouponRedemption.objects.filter(order=order).first()
    if redemption is None or redemption.released_at is None:
        return True
    claimed = (
        Coupon.objects.filter(pk=redemption.coupon_id)
        .filter(Q(usage_limit__isnull=True) | Q(times_used__lt=F("usage_limit")))
        .update(times_used=F("times_used") + 1)
    )
    if not claimed:
        return False
    CouponRedemption.objects.filter(pk=redemption.pk).update(released_at=None)
    return True
