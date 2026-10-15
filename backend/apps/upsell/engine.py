import logging
import time
from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from apps.tenancy.context import current_store

logger = logging.getLogger(__name__)

DEFAULT_PIPELINE = [
    {"strategy": "related_products"},
    {"strategy": "free_shipping_gap"},
    {"strategy": "coupon_unlock"},
]


@cache
def strategy(key):
    return import_string(settings.UPSELL_STRATEGIES[key])()


def pipeline_for(store):
    return store.upsell_config or DEFAULT_PIPELINE


def suggest_for_cart(view, *, limit=None, budget_ms=None):
    limit = limit or settings.UPSELL_MAX_SUGGESTIONS
    budget = (budget_ms or settings.UPSELL_TIME_BUDGET_MS) / 1000
    started = time.monotonic()
    in_cart = {item.product_id for item in view.items}
    seen_products = set()
    collected = []
    for entry in pipeline_for(current_store()):
        if time.monotonic() - started > budget:
            logger.warning("upsell_budget_exhausted skipped_from=%s", entry.get("strategy"))
            break
        key = entry.get("strategy")
        if key not in settings.UPSELL_STRATEGIES:
            logger.warning("upsell_unknown_strategy key=%s", key)
            continue
        try:
            suggestions = strategy(key).suggest(view, entry.get("config", {}))
        except Exception:
            logger.exception("upsell_strategy_failed key=%s", key)
            continue
        for suggestion in suggestions:
            product = suggestion.product
            if product is not None and (product.pk in in_cart or product.pk in seen_products):
                continue
            if product is not None:
                seen_products.add(product.pk)
            collected.append(suggestion)
    collected.sort(key=lambda suggestion: suggestion.score, reverse=True)
    return collected[:limit]
