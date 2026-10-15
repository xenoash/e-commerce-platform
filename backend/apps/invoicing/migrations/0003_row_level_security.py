from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("invoicing", "0002_initial")]

    operations = [
        enable_rls("invoicing_egsdevice", "invoicing_invoice"),
    ]
