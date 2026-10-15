from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("carts", "0002_initial")]

    operations = [
        enable_rls("carts_cart", "carts_cartitem"),
    ]
