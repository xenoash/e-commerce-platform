from django.apps import AppConfig


class TenancyConfig(AppConfig):
    name = "apps.tenancy"
    label = "tenancy"

    def ready(self):
        from celery.signals import task_postrun, task_prerun
        from django.db.backends.signals import connection_created

        from .context import (
            activate_tenant,
            apply_store_setting,
            current_store_id_or_none,
            current_store_or_none,
            reset_tenant,
        )

        def reapply_tenant(sender, connection, **kwargs):
            apply_store_setting(conn=connection, store_id=current_store_id_or_none())

        def isolate_task(task=None, **kwargs):
            task.request.tenancy_previous_store = current_store_or_none()
            reset_tenant()

        def restore_after_task(task=None, **kwargs):
            previous = getattr(task.request, "tenancy_previous_store", None)
            if previous is not None:
                activate_tenant(previous)
            else:
                reset_tenant()

        connection_created.connect(reapply_tenant, dispatch_uid="tenancy.reapply")
        task_prerun.connect(isolate_task, dispatch_uid="tenancy.prerun", weak=False)
        task_postrun.connect(restore_after_task, dispatch_uid="tenancy.postrun", weak=False)
