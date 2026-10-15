from contextlib import contextmanager
from contextvars import ContextVar

from django.db import connection, transaction

from apps.common.logging import store_handle_var

_current_store = ContextVar("current_store", default=None)
_bypass_active = ContextVar("rls_bypass_active", default=False)

STORE_GUC = "app.store_id"
BYPASS_GUC = "app.rls_bypass"


class TenantNotSet(RuntimeError):
    pass


class CrossTenantWrite(RuntimeError):
    pass


def current_store():
    store = _current_store.get()
    if store is None:
        raise TenantNotSet("No store is active for this operation.")
    return store


def current_store_or_none():
    return _current_store.get()


def current_store_id():
    return current_store().pk


def current_store_id_or_none():
    store = _current_store.get()
    return store.pk if store is not None else None


def bypass_active():
    return _bypass_active.get()


def apply_store_setting(conn=None, store_id=None):
    conn = conn or connection
    with conn.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, false)", [STORE_GUC, str(store_id) if store_id else ""])


def activate_tenant(store):
    token = _current_store.set(store)
    store_handle_var.set(store.handle if store is not None else "-")
    apply_store_setting(store_id=store.pk if store is not None else None)
    return token


def reset_tenant():
    _current_store.set(None)
    store_handle_var.set("-")
    apply_store_setting(store_id=None)


@contextmanager
def tenant_context(store):
    previous = _current_store.get()
    token = activate_tenant(store)
    try:
        yield store
    finally:
        _current_store.reset(token)
        store_handle_var.set(previous.handle if previous is not None else "-")
        apply_store_setting(store_id=previous.pk if previous is not None else None)


def _set_bypass(value):
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [BYPASS_GUC, value])


@contextmanager
def rls_bypass():
    with transaction.atomic():
        _set_bypass("on")
        token = _bypass_active.set(True)
        try:
            yield
        finally:
            _bypass_active.reset(token)
        _set_bypass("off")
