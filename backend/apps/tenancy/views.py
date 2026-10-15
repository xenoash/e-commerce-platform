from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.serializers import MONEY
from apps.tenancy.context import current_store


class StoreSerializer(serializers.Serializer):
    handle = serializers.CharField()
    name = serializers.CharField()
    currency = serializers.CharField()
    prices_include_vat = serializers.BooleanField()
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    shipping_fee = serializers.DecimalField(**MONEY)
    free_shipping_threshold = serializers.DecimalField(allow_null=True, **MONEY)
    b2b_enabled = serializers.BooleanField()


class StoreView(APIView):
    @extend_schema(
        operation_id="getStore",
        summary="Public settings of the current store",
        responses={200: StoreSerializer},
        tags=["Store"],
    )
    def get(self, request):
        store = current_store()
        return Response(
            StoreSerializer(
                {
                    "handle": store.handle,
                    "name": store.name,
                    "currency": store.currency,
                    "prices_include_vat": store.prices_include_vat,
                    "vat_rate": store.vat_rate,
                    "shipping_fee": store.shipping_fee,
                    "free_shipping_threshold": store.free_shipping_threshold,
                    "b2b_enabled": store.b2b_enabled,
                }
            ).data
        )
