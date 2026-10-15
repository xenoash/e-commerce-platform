import uuid

from django.db.models import Q
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts.services import hash_cart_token, request_customer
from apps.common.errors import ErrorCode, Problem
from apps.common.openapi import CART_TOKEN_HEADER, problem
from apps.invoicing.serializers import InvoiceSerializer, invoice_payload
from apps.invoicing.services import buyer_visible_invoice

from .checkout import confirm_payment
from .models import Order
from .serializers import OrderSerializer, order_payload


def load_order(request, order_id):
    try:
        order_uuid = uuid.UUID(str(order_id))
    except ValueError as exc:
        raise Problem(404, ErrorCode.ORDER_NOT_FOUND, "Order not found.") from exc
    condition = Q(pk__in=[])
    customer = request_customer(request)
    if customer is not None:
        condition |= Q(customer=customer)
    raw_token = request.headers.get("X-Cart-Token", "").strip()
    if raw_token:
        condition |= Q(customer__isnull=True, token_hash=hash_cart_token(raw_token))
    order = Order.objects.filter(condition, pk=order_uuid).first()
    if order is None:
        raise Problem(404, ErrorCode.ORDER_NOT_FOUND, "Order not found.")
    return order


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="listOrders",
        summary="The signed-in customer's orders",
        responses={200: OrderSerializer(many=True)},
        tags=["Orders"],
    )
    def get(self, request):
        orders = Order.objects.filter(customer=request.user).prefetch_related("lines")[:50]
        return Response(OrderSerializer([order_payload(order) for order in orders], many=True).data)


class OrderDetailView(APIView):
    @extend_schema(
        operation_id="getOrder",
        summary="Get an order with its payment and invoice status",
        parameters=[CART_TOKEN_HEADER],
        responses={200: OrderSerializer, 404: problem("Order not found.")},
        tags=["Orders"],
    )
    def get(self, request, order_id):
        return Response(OrderSerializer(order_payload(load_order(request, order_id))).data)


class OrderPaymentConfirmView(APIView):
    @extend_schema(
        operation_id="confirmOrderPayment",
        summary="Re-check payment with the gateway after a redirect (safe to call repeatedly)",
        parameters=[CART_TOKEN_HEADER],
        request=None,
        responses={200: OrderSerializer, 404: problem("Order not found.")},
        tags=["Orders"],
    )
    def post(self, request, order_id):
        order = confirm_payment(load_order(request, order_id))
        return Response(OrderSerializer(order_payload(order)).data)


class OrderInvoiceView(APIView):
    @extend_schema(
        operation_id="getOrderInvoice",
        summary="The order's ZATCA tax invoice (JSON with QR payload, or ?format=xml for the signed UBL)",
        parameters=[
            CART_TOKEN_HEADER,
            OpenApiParameter("format", str, OpenApiParameter.QUERY, required=False, enum=["json", "xml"]),
        ],
        responses={
            200: InvoiceSerializer,
            404: problem("Order not found."),
            409: problem("Invoice not issued or not cleared yet."),
        },
        tags=["Orders"],
    )
    def get(self, request, order_id):
        invoice = buyer_visible_invoice(load_order(request, order_id))
        if request.query_params.get("format") == "xml":
            response = HttpResponse(invoice.document_xml(), content_type="application/xml; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{invoice.number}.xml"'
            return response
        return Response(InvoiceSerializer(invoice_payload(invoice)).data)
