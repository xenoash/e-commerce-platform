from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("customers", "0001_initial")]

    operations = [
        enable_rls("customers_customer", "customers_accesstoken"),
    ]
