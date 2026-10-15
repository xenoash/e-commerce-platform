from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("orders", "0002_initial")]

    operations = [
        migrations.RunSQL(
            "CREATE SEQUENCE IF NOT EXISTS order_number_seq START WITH 100001",
            reverse_sql="DROP SEQUENCE IF EXISTS order_number_seq",
        ),
        enable_rls("orders_order", "orders_orderline"),
    ]
