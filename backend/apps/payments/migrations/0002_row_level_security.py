from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [
        enable_rls("payments_storepaymentmethod", "payments_payment", "payments_webhookevent"),
    ]
