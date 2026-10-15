import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
store_handle_var: ContextVar[str] = ContextVar("store_handle", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        record.store = store_handle_var.get()
        return True
