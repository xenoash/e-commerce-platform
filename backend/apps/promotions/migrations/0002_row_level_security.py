from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("promotions", "0001_initial")]

    operations = [
        enable_rls("promotions_coupon", "promotions_couponredemption"),
    ]
