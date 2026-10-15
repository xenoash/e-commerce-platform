from rest_framework import serializers

from apps.carts.serializers import MONEY


class ProductSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField()
    name_ar = serializers.CharField(allow_blank=True, help_text="Arabic name, when the store provides one.")
    description = serializers.CharField(allow_blank=True)
    kind = serializers.CharField()
    price = serializers.DecimalField(**MONEY, help_text="In the store's price basis (see GET /store).")
    in_stock = serializers.BooleanField()
    stock_level = serializers.IntegerField(allow_null=True, help_text="Units available, or null when not tracked.")
    max_per_order = serializers.IntegerField()
    image_url = serializers.CharField(allow_blank=True)


def product_payload(product):
    return {
        "id": product.pk,
        "sku": product.sku,
        "name": product.name,
        "name_ar": product.name_ar,
        "description": product.description,
        "kind": product.kind,
        "price": product.price,
        "in_stock": product.in_stock,
        "stock_level": product.stock if product.track_stock else None,
        "max_per_order": product.max_per_order,
        "image_url": product.image_url,
    }


class ProductPageSerializer(serializers.Serializer):
    next = serializers.URLField(allow_null=True, help_text="Absolute URL of the next page, or null.")
    previous = serializers.URLField(allow_null=True)
    results = ProductSerializer(many=True)
