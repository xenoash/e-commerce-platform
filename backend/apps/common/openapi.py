from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse
from rest_framework import serializers

STORE_HEADER = OpenApiParameter(
    "X-Store",
    str,
    OpenApiParameter.HEADER,
    required=True,
    description="Handle of the store (tenant) this request is for.",
)
CART_TOKEN_HEADER = OpenApiParameter(
    "X-Cart-Token",
    str,
    OpenApiParameter.HEADER,
    required=False,
    description="Secret returned when a guest cart is created. Not needed for signed-in customers.",
)
IF_MATCH_HEADER = OpenApiParameter(
    "If-Match",
    str,
    OpenApiParameter.HEADER,
    required=False,
    description='Cart version from the last read (ETag), for example "7". A stale version returns 412.',
)
IDEMPOTENCY_KEY_HEADER = OpenApiParameter(
    "Idempotency-Key",
    str,
    OpenApiParameter.HEADER,
    required=True,
    description="Unique per checkout attempt. Retrying with the same key never creates a second order.",
)


class FieldErrorSerializer(serializers.Serializer):
    field = serializers.CharField(allow_null=True)
    code = serializers.CharField()
    message = serializers.CharField()


class ProblemSerializer(serializers.Serializer):
    type = serializers.CharField()
    title = serializers.CharField()
    status = serializers.IntegerField()
    code = serializers.CharField(help_text="Stable machine-readable error code.")
    detail = serializers.CharField(required=False)
    errors = FieldErrorSerializer(many=True, required=False)


def problem(description):
    return OpenApiResponse(ProblemSerializer, description=description)


class TenantAutoSchema(AutoSchema):
    def get_override_parameters(self):
        parameters = super().get_override_parameters()
        if self.path.startswith("/api/v1/webhooks/"):
            return parameters
        return [STORE_HEADER, *parameters]
