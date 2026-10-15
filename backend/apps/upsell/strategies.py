from decimal import Decimal

from apps.catalog.models import Product, ProductRecommendation
from apps.common.money import format_amount
from apps.promotions.models import Coupon
from apps.promotions.rules import MinSubtotal, build_rules
from apps.tenancy.context import current_store

from .base import Suggestion, UpsellStrategy


def _in_cart(view):
    return {item.product_id for item in view.items}


def _sellable(queryset):
    return queryset.filter(is_active=True).exclude(track_stock=True, stock=0)


class RelatedProductsStrategy(UpsellStrategy):
    key = "related_products"

    def suggest(self, view, config):
        in_cart = _in_cart(view)
        if not in_cart:
            return []
        limit = int(config.get("limit", 4))
        recommendations = (
            ProductRecommendation.objects.select_related("product", "recommended")
            .filter(product_id__in=in_cart, recommended__is_active=True)
            .exclude(recommended_id__in=in_cart)
            .order_by("position")[: limit * 2]
        )
        suggestions = []
        for rank, recommendation in enumerate(recommendations):
            product = recommendation.recommended
            if product.track_stock and product.stock == 0:
                continue
            suggestions.append(
                Suggestion(
                    strategy=self.key,
                    type="product",
                    headline=recommendation.headline or f"Goes well with {recommendation.product.name}",
                    reason_code="FREQUENTLY_BOUGHT_TOGETHER",
                    score=100 - rank,
                    product=product,
                )
            )
        return suggestions[:limit]


class FreeShippingGapStrategy(UpsellStrategy):
    key = "free_shipping_gap"

    def suggest(self, view, config):
        configured = config.get("threshold")
        threshold = Decimal(str(configured)) if configured else current_store().free_shipping_threshold
        if threshold is None or not view.requires_shipping:
            return []
        merchandise = view.priced.subtotal - view.priced.item_discount
        remaining = threshold - merchandise
        if remaining <= 0:
            return []
        suggestions = [
            Suggestion(
                strategy=self.key,
                type="message",
                headline=f"Add {format_amount(remaining)} more for free shipping",
                reason_code="FREE_SHIPPING_GAP",
                score=90,
                data={"remaining": format_amount(remaining), "threshold": format_amount(threshold)},
            )
        ]
        fillers = (
            _sellable(Product.objects.filter(price__gte=remaining, kind=Product.Kind.PHYSICAL))
            .exclude(pk__in=_in_cart(view))
            .order_by("price", "id")[: int(config.get("limit", 2))]
        )
        for rank, product in enumerate(fillers):
            suggestions.append(
                Suggestion(
                    strategy=self.key,
                    type="product",
                    headline="Unlocks free shipping",
                    reason_code="CLOSES_FREE_SHIPPING_GAP",
                    score=80 - rank,
                    product=product,
                )
            )
        return suggestions


class CouponUnlockStrategy(UpsellStrategy):
    key = "coupon_unlock"

    def suggest(self, view, config):
        if view.cart.coupon_id:
            return []
        subtotal = view.priced.subtotal
        suggestions = []
        for coupon in Coupon.objects.filter(advertise=True, is_active=True)[:20]:
            minimum = next((rule.amount for rule in build_rules(coupon.rules) if isinstance(rule, MinSubtotal)), None)
            if minimum is None or subtotal >= minimum:
                continue
            remaining = minimum - subtotal
            suggestions.append(
                Suggestion(
                    strategy=self.key,
                    type="message",
                    headline=f"Spend {format_amount(remaining)} more to use {coupon.code}: {coupon.description}".rstrip(
                        ": "
                    ),
                    reason_code="COUPON_UNLOCK",
                    score=85,
                    data={"coupon_code": coupon.code, "remaining": format_amount(remaining)},
                )
            )
        return suggestions[: int(config.get("limit", 1))]


class ServiceAddonsStrategy(UpsellStrategy):
    key = "service_addons"

    def suggest(self, view, config):
        if not view.requires_shipping:
            return []
        addons = (
            _sellable(Product.objects.filter(is_addon=True))
            .exclude(pk__in=_in_cart(view))
            .order_by("price")[: int(config.get("limit", 2))]
        )
        return [
            Suggestion(
                strategy=self.key,
                type="product",
                headline=f"Add {product.name.lower()}",
                reason_code="SERVICE_ADDON",
                score=70 - rank,
                product=product,
            )
            for rank, product in enumerate(addons)
        ]
