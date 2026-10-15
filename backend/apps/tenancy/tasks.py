from celery import shared_task

from .context import tenant_context
from .models import Store


def tenant_task(*task_args, **task_kwargs):
    def decorator(func):
        def run(*args, store_id, **kwargs):
            store = Store.objects.get(pk=store_id)
            with tenant_context(store):
                return func(*args, **kwargs)

        run.__name__ = func.__name__
        run.__qualname__ = func.__qualname__
        run.__module__ = func.__module__
        run.__doc__ = func.__doc__
        return shared_task(*task_args, **task_kwargs)(run)

    return decorator
