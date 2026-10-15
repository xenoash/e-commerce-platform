from rest_framework import serializers

from apps.catalog.serializers import ProductSerializer, product_payload


class SuggestionActionSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["add_item"])
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField()


class SuggestionSerializer(serializers.Serializer):
    strategy = serializers.CharField()
    type = serializers.ChoiceField(choices=["product", "message"])
    headline = serializers.CharField()
    reason_code = serializers.CharField()
    product = ProductSerializer(allow_null=True)
    action = SuggestionActionSerializer(allow_null=True)
    data = serializers.DictField()


class SuggestionListSerializer(serializers.Serializer):
    suggestions = SuggestionSerializer(many=True)


def suggestions_payload(suggestions):
    return {
        "suggestions": [
            {
                "strategy": s.strategy,
                "type": s.type,
                "headline": s.headline,
                "reason_code": s.reason_code,
                "product": product_payload(s.product) if s.product is not None else None,
                "action": {"type": "add_item", "product_id": s.product.pk, "quantity": 1}
                if s.product is not None
                else None,
                "data": s.data,
            }
            for s in suggestions
        ]
    }
