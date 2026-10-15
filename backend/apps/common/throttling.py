from rest_framework.throttling import SimpleRateThrottle

from apps.tenancy.context import current_store_id_or_none


class StoreRateThrottle(SimpleRateThrottle):
    scope = "store"

    def get_cache_key(self, request, view):
        store_id = current_store_id_or_none()
        if store_id is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(store_id)}
