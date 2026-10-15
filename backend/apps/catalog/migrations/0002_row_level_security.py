from django.db import migrations

from apps.tenancy.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        enable_rls("catalog_product", "catalog_productrecommendation"),
    ]
