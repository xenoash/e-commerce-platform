import logging
import uuid

from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorCode, Problem
from apps.common.openapi import problem
from apps.orders.lifecycle import apply_payment_result
from apps.tenancy.context import current_store

from .base import GatewayContext, InvalidSignature
from .models import Payment, StorePaymentMethod, WebhookEvent
from .registry import gateway_class

logger = logging.getLogger(__name__)


class PaymentMethodSerializer(serializers.Serializer):
    method = serializers.CharField()
    gateway = serializers.CharField()
    display_name = serializers.CharField()
    requires_token = serializers.BooleanField()


class PaymentMethodListView(APIView):
    @extend_schema(
        operation_id="listPaymentMethods",
        summary="Payment methods this store accepts",
        responses={200: PaymentMethodSerializer(many=True)},
        tags=["Store"],
    )
    def get(self, request):
        methods = StorePaymentMethod.objects.filter(is_enabled=True)
        payload = [
            {
                "method": m.method,
                "gateway": m.gateway,
                "display_name": m.display_name,
                "requires_token": gateway_class(m.gateway).requires_token,
            }
            for m in methods
        ]
        return Response(PaymentMethodSerializer(payload, many=True).data)


class WebhookAckSerializer(serializers.Serializer):
    received = serializers.BooleanField()
    outcome = serializers.ChoiceField(choices=["applied", "duplicate", "ignored"])


def _parse_reference(reference):
    try:
        return uuid.UUID(str(reference))
    except ValueError:
        return None


class PaymentWebhookView(APIView):
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        operation_id="receivePaymentWebhook",
        summary="Gateway callback. Signature-verified with the store's secret; duplicates are no-ops.",
        request=None,
        responses={200: WebhookAckSerializer, 401: problem("Signature invalid.")},
        tags=["Webhooks"],
    )
    def post(self, request, gateway, store):
        body = request.body
        configured = StorePaymentMethod.objects.filter(gateway=gateway).first()
        context = GatewayContext(
            store_id=str(current_store().pk),
            store_handle=current_store().handle,
            method=configured.method if configured else "",
            config=configured.config if configured else {},
        )
        handler = gateway_class(gateway)(context)
        try:
            event = handler.parse_webhook(body, request.headers)
        except InvalidSignature as exc:
            logger.warning("webhook_signature_invalid gateway=%s reason=%s", gateway, exc)
            raise Problem(401, ErrorCode.WEBHOOK_SIGNATURE_INVALID, "Webhook signature is invalid.") from exc
        if event is None:
            return Response({"received": True, "outcome": "ignored"})
        reference = _parse_reference(event.reference)
        payment = Payment.objects.filter(pk=reference, gateway=gateway).first() if reference else None
        if payment is None:
            logger.warning("webhook_unknown_payment gateway=%s reference=%s", gateway, event.reference)
            return Response({"received": True, "outcome": "ignored"})
        with transaction.atomic():
            try:
                with transaction.atomic():
                    WebhookEvent.objects.create(gateway=gateway, event_id=event.event_id, payment=payment)
            except IntegrityError:
                return Response({"received": True, "outcome": "duplicate"})
            apply_payment_result(payment.pk, event.result)
        return Response({"received": True, "outcome": "applied"})
