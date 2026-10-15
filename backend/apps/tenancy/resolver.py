from django.core.cache import cache

from .models import Store

CACHE_TTL_SECONDS = 60


def _cache_key(handle):
    return f"store:handle:{handle}"


def resolve_store(handle):
    if not handle or len(handle) > 63:
        return None
    key = _cache_key(handle)
    store = cache.get(key)
    if store is None:
        store = Store.objects.filter(handle=handle, is_active=True).first()
        if store is not None:
            cache.set(key, store, CACHE_TTL_SECONDS)
    return store


def forget_store(handle):
    cache.delete(_cache_key(handle))
