from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.openapi import CART_TOKEN_HEADER, IDEMPOTENCY_KEY_HEADER, IF_MATCH_HEADER, problem
from apps.orders.checkout import CheckoutInput, checkout
from apps.orders.serializers import OrderSerializer, order_payload
from apps.upsell.engine import suggest_for_cart
from apps.upsell.serializers import SuggestionListSerializer, suggestions_payload

from . import services
from .serializers import (
    AddItemSerializer,
    AddressSerializer,
    ApplyCouponSerializer,
    BillingAddressSerializer,
    CartSerializer,
    CheckoutSerializer,
    CreatedCartSerializer,
    PaymentMethodInputSerializer,
    UpdateItemSerializer,
    cart_payload,
)

CART_ERRORS = {
    404: problem("Cart not found, or it belongs to another customer or store."),
    409: problem("The cart is not open, or the change conflicts with stock."),
    412: problem("If-Match did not match the current cart version."),
}


def cart_response(view, *, status=200, cart_token=None, created_shape=False):
    payload = cart_payload(view)
    serializer_class = CartSerializer
    if created_shape:
        payload["cart_token"] = cart_token
        serializer_class = CreatedCartSerializer
    response = Response(serializer_class(payload).data, status=status)
    response["ETag"] = f'"{view.cart.version}"'
    return response


def validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def mutate(request, cart_id, action):
    with services.mutate_cart(request, cart_id) as cart:
        action(cart)
    return cart_response(services.build_cart_view(cart))


class CartCollectionView(APIView):
    @extend_schema(
        operation_id="createCart",
        summary="Open a cart",
        description=(
            "Signed-in customers get their active cart back (200) or a new one (201). "
            "Guests always get a new cart and a one-time `cart_token`."
        ),
        request=None,
        responses={201: CreatedCartSerializer, 200: CreatedCartSerializer},
        tags=["Carts"],
    )
    def post(self, request):
        cart, created, raw_token = services.open_or_create_cart(request)
        return cart_response(
            services.build_cart_view(cart), status=201 if created else 200, cart_token=raw_token, created_shape=True
        )


class CartDetailView(APIView):
    @extend_schema(
        operation_id="getCart",
        summary="Get a cart with live prices, warnings and checkout readiness",
        parameters=[CART_TOKEN_HEADER],
        responses={200: CartSerializer, 404: CART_ERRORS[404]},
        tags=["Carts"],
    )
    def get(self, request, cart_id):
        return cart_response(services.build_cart_view(services.load_cart(request, cart_id)))


class CartItemsView(APIView):
    @extend_schema(
        operation_id="addCartItem",
        summary="Add a product (merges into the existing line)",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=AddItemSerializer,
        responses={200: CartSerializer, 422: problem("Unknown product or quantity limit."), **CART_ERRORS},
        tags=["Carts"],
    )
    def post(self, request, cart_id):
        data = validated(AddItemSerializer, request)
        return mutate(request, cart_id, lambda cart: services.add_item(cart, data["product_id"], data["quantity"]))


class CartItemDetailView(APIView):
    @extend_schema(
        operation_id="updateCartItem",
        summary="Change a line's quantity",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=UpdateItemSerializer,
        responses={200: CartSerializer, **CART_ERRORS},
        tags=["Carts"],
    )
    def patch(self, request, cart_id, item_id):
        data = validated(UpdateItemSerializer, request)
        return mutate(request, cart_id, lambda cart: services.set_item_quantity(cart, item_id, data["quantity"]))

    @extend_schema(
        operation_id="removeCartItem",
        summary="Remove a product",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=None,
        responses={200: CartSerializer, **CART_ERRORS},
        tags=["Carts"],
    )
    def delete(self, request, cart_id, item_id):
        return mutate(request, cart_id, lambda cart: services.remove_item(cart, item_id))


class CartCouponView(APIView):
    @extend_schema(
        operation_id="applyCoupon",
        summary="Apply a coupon (replaces any applied coupon)",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=ApplyCouponSerializer,
        responses={200: CartSerializer, 422: problem("Unknown coupon or a failed constraint."), **CART_ERRORS},
        tags=["Carts"],
    )
    def put(self, request, cart_id):
        data = validated(ApplyCouponSerializer, request)
        return mutate(request, cart_id, lambda cart: services.apply_coupon(cart, data["code"]))

    @extend_schema(
        operation_id="removeCoupon",
        summary="Remove the coupon (no-op when none is applied)",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=None,
        responses={200: CartSerializer, **CART_ERRORS},
        tags=["Carts"],
    )
    def delete(self, request, cart_id):
        return mutate(request, cart_id, services.remove_coupon)


class CartShippingAddressView(APIView):
    @extend_schema(
        operation_id="setShippingAddress",
        summary="Set the delivery address (Saudi national address)",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=AddressSerializer,
        responses={200: CartSerializer, **CART_ERRORS},
        tags=["Carts"],
    )
    def put(self, request, cart_id):
        data = validated(AddressSerializer, request)
        return mutate(request, cart_id, lambda cart: setattr(cart, "shipping_address", data))


class CartBillingAddressView(APIView):
    @extend_schema(
        operation_id="setBillingAddress",
        summary="Set the billing address; a VAT number makes the invoice a standard (B2B) tax invoice",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=BillingAddressSerializer,
        responses={200: CartSerializer, **CART_ERRORS},
        tags=["Carts"],
    )
    def put(self, request, cart_id):
        data = validated(BillingAddressSerializer, request)
        return mutate(request, cart_id, lambda cart: setattr(cart, "billing_address", data))


class CartPaymentMethodView(APIView):
    @extend_schema(
        operation_id="setPaymentMethod",
        summary="Choose how to pay (the card token is sent at checkout, never stored on the cart)",
        parameters=[CART_TOKEN_HEADER, IF_MATCH_HEADER],
        request=PaymentMethodInputSerializer,
        responses={
            200: CartSerializer,
            422: problem("Method not offered or not allowed for this customer."),
            **CART_ERRORS,
        },
        tags=["Carts"],
    )
    def put(self, request, cart_id):
        data = validated(PaymentMethodInputSerializer, request)
        return mutate(request, cart_id, lambda cart: services.set_payment_method(cart, data["method"]))


class CartSuggestionsView(APIView):
    @extend_schema(
        operation_id="listCartSuggestions",
        summary="Upsell and cross-sell suggestions for this cart",
        parameters=[CART_TOKEN_HEADER],
        responses={200: SuggestionListSerializer, 404: CART_ERRORS[404]},
        tags=["Carts"],
    )
    def get(self, request, cart_id):
        view = services.build_cart_view(services.load_cart(request, cart_id))
        return Response(SuggestionListSerializer(suggestions_payload(suggest_for_cart(view))).data)


class CartCheckoutView(APIView):
    @extend_schema(
        operation_id="checkoutCart",
        summary="Place the order and start payment",
        description=(
            "Creates an order and charges the chosen payment method. Returns 201 with the order. "
            "When `payment.next_action` is present, send the shopper there (3-D Secure), then call "
            "`POST /orders/{id}/payment/confirm`. Retrying with the same Idempotency-Key replays the result."
        ),
        parameters=[CART_TOKEN_HEADER, IDEMPOTENCY_KEY_HEADER],
        request=CheckoutSerializer,
        responses={
            201: OrderSerializer,
            200: OrderSerializer,
            409: problem(
                "Cart not ready, total changed, out of stock, coupon no longer applies, or request in progress."
            ),
            422: problem("Payment token missing, method not allowed, or Idempotency-Key reused with another body."),
            428: problem("Idempotency-Key header missing."),
        },
        tags=["Checkout"],
    )
    def post(self, request, cart_id):
        data = validated(CheckoutSerializer, request)
        outcome = checkout(
            request,
            cart_id,
            CheckoutInput(
                payment_token=data.get("payment_token"),
                expected_total=data.get("expected_total"),
                po_number=data.get("po_number", ""),
            ),
        )
        response = Response(OrderSerializer(order_payload(outcome.order)).data, status=outcome.status_code)
        response["Location"] = f"/api/v1/orders/{outcome.order.pk}"
        if outcome.replayed:
            response["Idempotent-Replayed"] = "true"
        return response
