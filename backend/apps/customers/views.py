from django.contrib.auth.hashers import make_password
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.serializers import MONEY
from apps.common.errors import ErrorCode, Problem
from apps.common.openapi import problem

from .models import Customer
from .tokens import issue_token

TIMING_SAFE_HASH = make_password("timing-safe-placeholder")


class TokenRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class CustomerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    kind = serializers.CharField()
    company_name = serializers.CharField(allow_blank=True)
    vat_number = serializers.CharField(allow_blank=True)
    credit_approved = serializers.BooleanField()
    credit_limit = serializers.DecimalField(**MONEY)


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    token_type = serializers.CharField()
    expires_at = serializers.DateTimeField()
    customer = CustomerSerializer()


def customer_payload(customer):
    return {
        "id": customer.pk,
        "email": customer.email,
        "name": customer.name,
        "kind": customer.kind,
        "company_name": customer.company_name,
        "vat_number": customer.vat_number,
        "credit_approved": customer.credit_approved,
        "credit_limit": customer.credit_limit,
    }


class TokenView(APIView):
    authentication_classes = []

    @extend_schema(
        operation_id="createToken",
        summary="Sign in and get a store-scoped bearer token",
        request=TokenRequestSerializer,
        responses={201: TokenResponseSerializer, 401: problem("Wrong email or password for this store.")},
        tags=["Auth"],
    )
    def post(self, request):
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = Customer.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        password = serializer.validated_data["password"]
        if customer is None:
            Customer(password=TIMING_SAFE_HASH).check_password(password)
            raise Problem(401, ErrorCode.INVALID_CREDENTIALS, "Wrong email or password for this store.")
        if not customer.check_password(password):
            raise Problem(401, ErrorCode.INVALID_CREDENTIALS, "Wrong email or password for this store.")
        raw, token = issue_token(customer)
        payload = {
            "token": raw,
            "token_type": "Bearer",
            "expires_at": token.expires_at,
            "customer": customer_payload(customer),
        }
        return Response(TokenResponseSerializer(payload).data, status=201)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="getMe", summary="The signed-in customer", responses={200: CustomerSerializer}, tags=["Auth"]
    )
    def get(self, request):
        return Response(CustomerSerializer(customer_payload(request.user)).data)
