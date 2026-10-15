from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from apps.common.errors import ErrorCode, Problem

from .base import GatewayContext


@cache
def gateway_class(key):
    path = settings.PAYMENT_GATEWAYS.get(key)
    if path is None:
        raise Problem(404, ErrorCode.GATEWAY_NOT_FOUND, f"Unknown payment gateway '{key}'.")
    return import_string(path)


def gateway_for(store, method_config):
    context = GatewayContext(
        store_id=str(store.pk),
        store_handle=store.handle,
        method=method_config.method,
        config=method_config.config,
    )
    return gateway_class(method_config.gateway)(context)
