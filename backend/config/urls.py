from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.carts import views as carts
from apps.catalog import views as catalog
from apps.common.health import healthz, readyz
from apps.customers import views as customers
from apps.orders import views as orders
from apps.payments import simulator
from apps.payments import views as payments
from apps.tenancy import views as tenancy

api_v1 = [
    path("store", tenancy.StoreView.as_view(), name="store"),
    path("payment-methods", payments.PaymentMethodListView.as_view(), name="payment-methods"),
    path("auth/token", customers.TokenView.as_view(), name="auth-token"),
    path("me", customers.MeView.as_view(), name="me"),
    path("products", catalog.ProductListView.as_view(), name="products"),
    path("products/<uuid:product_id>", catalog.ProductDetailView.as_view(), name="product-detail"),
    path("carts", carts.CartCollectionView.as_view(), name="carts"),
    path("carts/<str:cart_id>", carts.CartDetailView.as_view(), name="cart-detail"),
    path("carts/<str:cart_id>/items", carts.CartItemsView.as_view(), name="cart-items"),
    path("carts/<str:cart_id>/items/<str:item_id>", carts.CartItemDetailView.as_view(), name="cart-item-detail"),
    path("carts/<str:cart_id>/coupon", carts.CartCouponView.as_view(), name="cart-coupon"),
    path("carts/<str:cart_id>/shipping-address", carts.CartShippingAddressView.as_view(), name="cart-shipping-address"),
    path("carts/<str:cart_id>/billing-address", carts.CartBillingAddressView.as_view(), name="cart-billing-address"),
    path("carts/<str:cart_id>/payment-method", carts.CartPaymentMethodView.as_view(), name="cart-payment-method"),
    path("carts/<str:cart_id>/suggestions", carts.CartSuggestionsView.as_view(), name="cart-suggestions"),
    path("carts/<str:cart_id>/checkout", carts.CartCheckoutView.as_view(), name="cart-checkout"),
    path("orders", orders.OrderListView.as_view(), name="orders"),
    path("orders/<str:order_id>", orders.OrderDetailView.as_view(), name="order-detail"),
    path(
        "orders/<str:order_id>/payment/confirm", orders.OrderPaymentConfirmView.as_view(), name="order-payment-confirm"
    ),
    path("orders/<str:order_id>/invoice", orders.OrderInvoiceView.as_view(), name="order-invoice"),
    path(
        "webhooks/payments/<slug:gateway>/<slug:store>", payments.PaymentWebhookView.as_view(), name="payment-webhook"
    ),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
    path("healthz", healthz),
    path("readyz", readyz),
    path("sim/fakepay/3ds/<str:charge_id>", simulator.three_d_secure, name="fakepay-3ds"),
]
