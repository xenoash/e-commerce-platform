import re

from apps.common.errors import ErrorCode, Problem, problem_json_response

from .context import activate_tenant, current_store_or_none, reset_tenant
from .resolver import resolve_store

API_PREFIX = "/api/v1/"
WEBHOOK_PATH = re.compile(r"^/api/v1/webhooks/payments/[a-z0-9_]+/(?P<store>[a-z0-9-]+)/?$")
PUBLIC_API_PATHS = ("/api/v1/schema", "/api/v1/docs")


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        handle = self._store_handle(request)
        if handle is None:
            return self.get_response(request)
        if handle == "":
            return problem_json_response(
                Problem(400, ErrorCode.STORE_HEADER_MISSING, "Send the store handle in the X-Store header.")
            )
        store = resolve_store(handle)
        if store is None:
            return problem_json_response(Problem(404, ErrorCode.STORE_NOT_FOUND, f"No active store '{handle}'."))
        previous = current_store_or_none()
        activate_tenant(store)
        request.store = store
        try:
            return self.get_response(request)
        finally:
            if previous is None:
                reset_tenant()
            else:
                activate_tenant(previous)

    def _store_handle(self, request):
        path = request.path
        if not path.startswith(API_PREFIX) or path.startswith(PUBLIC_API_PATHS):
            return None
        webhook = WEBHOOK_PATH.match(path)
        if webhook:
            return webhook.group("store")
        return request.headers.get("X-Store", "").strip().lower()
