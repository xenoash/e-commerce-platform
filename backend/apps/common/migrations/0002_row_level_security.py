from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("common", "0001_initial")]

    operations = [
        enable_rls("common_idempotencyrecord"),
    ]
