import hashlib
import re
import secrets
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.catalog.models import Product
from apps.common.errors import ErrorCode, Problem
from apps.common.money import ZERO, format_amount
from apps.payments.models import StorePaymentMethod
from apps.payments.registry import gateway_for
from apps.promotions.services import evaluate_coupon, find_coupon
from apps.tenancy.context import current_store

from .models import Cart, CartItem
from .pricing import PricingLine, PricingPolicy, price_cart

CART_TOKEN_PREFIX = "ctk_"
IF_MATCH_PATTERN = re.compile(r'^(?:W/)?"?(\d+)"?$')


def hash_cart_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_cart_token():
    raw = CART_TOKEN_PREFIX + secrets.token_urlsafe(24)
    return raw, hash_cart_token(raw)


def request_customer(request):
    return request.user if getattr(request.user, "is_authenticated", False) else None


def ownership_filter(request):
    condition = Q(pk__in=[])
    customer = request_customer(request)
    if customer is not None:
        condition |= Q(customer=customer)
    raw_token = request.headers.get("X-Cart-Token", "").strip()
    if raw_token:
        condition |= Q(customer__isnull=True, token_hash=hash_cart_token(raw_token))
    return condition


def _parse_uuid(value, code):
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise Problem(404, code, "The requested resource does not exist.") from exc


def load_cart(request, cart_id, *, lock=False):
    queryset = Cart.objects.filter(ownership_filter(request))
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    cart = queryset.filter(pk=_parse_uuid(cart_id, ErrorCode.CART_NOT_FOUND)).first()
    if cart is None:
        raise Problem(404, ErrorCode.CART_NOT_FOUND, "No cart with this id belongs to you in this store.")
    return cart


def open_or_create_cart(request):
    customer = request_customer(request)
    if customer is None:
        raw, digest = issue_cart_token()
        return Cart.objects.create(token_hash=digest), True, raw
    existing = Cart.objects.filter(customer=customer, status__in=Cart.ACTIVE_STATUSES).first()
    if existing is not None:
        return existing, False, None
    try:
        with transaction.atomic():
            return Cart.objects.create(customer=customer), True, None
    except IntegrityError:
        return Cart.objects.get(customer=customer, status__in=Cart.ACTIVE_STATUSES), False, None


def check_precondition(request, cart):
    header = request.headers.get("If-Match", "").strip()
    if not header or header == "*":
        return
    match = IF_MATCH_PATTERN.match(header)
    if match is None or int(match.group(1)) != cart.version:
        raise Problem(
            412,
            ErrorCode.CART_VERSION_MISMATCH,
            "The cart changed since you last read it. Fetch it again and retry.",
            current_version=cart.version,
        )


def require_open(cart):
    if not cart.is_open:
        raise Problem(409, ErrorCode.CART_NOT_OPEN, f"The cart is {cart.status} and can no longer be changed.")


@contextmanager
def mutate_cart(request, cart_id):
    with transaction.atomic():
        cart = load_cart(request, cart_id, lock=True)
        check_precondition(request, cart)
        require_open(cart)
        yield cart
        cart.version += 1
        cart.save()


def _active_product(product_id):
    product = Product.objects.filter(pk=product_id, is_active=True).first()
    if product is None:
        raise Problem(422, ErrorCode.PRODUCT_NOT_FOUND, "This product does not exist or is not for sale.")
    return product


def _check_quantity(product, quantity):
    if quantity > product.max_per_order:
        raise Problem(
            422,
            ErrorCode.QUANTITY_LIMIT_EXCEEDED,
            f"You can buy at most {product.max_per_order} of this product per order.",
            max_per_order=product.max_per_order,
        )
    if product.track_stock and quantity > product.stock:
        raise Problem(
            409,
            ErrorCode.OUT_OF_STOCK,
            f"Only {product.stock} left in stock.",
            items=[{"product_id": str(product.pk), "requested": quantity, "available": product.stock}],
        )


def add_item(cart, product_id, quantity):
    product = _active_product(product_id)
    item = CartItem.objects.filter(cart=cart, product=product).first()
    new_quantity = quantity + (item.quantity if item else 0)
    _check_quantity(product, new_quantity)
    if item is None:
        return CartItem.objects.create(cart=cart, product=product, quantity=new_quantity, unit_price_seen=product.price)
    item.quantity = new_quantity
    item.unit_price_seen = product.price
    item.save(update_fields=["quantity", "unit_price_seen"])
    return item


def _cart_item(cart, item_id):
    item = (
        CartItem.objects.select_related("product")
        .filter(cart=cart, pk=_parse_uuid(item_id, ErrorCode.CART_ITEM_NOT_FOUND))
        .first()
    )
    if item is None:
        raise Problem(404, ErrorCode.CART_ITEM_NOT_FOUND, "This item is not in the cart.")
    return item


def set_item_quantity(cart, item_id, quantity):
    item = _cart_item(cart, item_id)
    _check_quantity(item.product, quantity)
    item.quantity = quantity
    item.unit_price_seen = item.product.price
    item.save(update_fields=["quantity", "unit_price_seen"])
    return item


def remove_item(cart, item_id):
    _cart_item(cart, item_id).delete()


def apply_coupon(cart, code):
    coupon = find_coupon(code)
    view = build_cart_view(cart, coupon_override=coupon)
    if view.coupon is not None and not view.coupon.applicable:
        raise view.coupon.problem
    cart.coupon = coupon


def remove_coupon(cart):
    cart.coupon = None


def set_payment_method(cart, method):
    config = StorePaymentMethod.objects.filter(method=method, is_enabled=True).first()
    if config is None:
        raise Problem(422, ErrorCode.PAYMENT_METHOD_NOT_AVAILABLE, "This store does not offer this payment method.")
    view = build_cart_view(cart)
    problem = gateway_for(current_store(), config).eligibility_problem(cart.customer, view.priced.total)
    if problem is not None:
        raise problem
    cart.payment_method = method


def requires_standard_invoice(cart):
    if cart.customer is not None and cart.customer.is_business:
        return True
    return bool((cart.billing_address or {}).get("vat_number"))


def billing_complete_for_standard_invoice(address):
    if not address:
        return False
    required = ("company_name", "vat_number", "street", "building_number", "district", "city", "postal_code")
    return all(address.get(key) for key in required)


def pricing_policy(store):
    return PricingPolicy(
        prices_include_vat=store.prices_include_vat,
        vat_rate=store.vat_rate,
        shipping_fee=store.shipping_fee,
        free_shipping_threshold=store.free_shipping_threshold,
    )


@dataclass
class CartView:
    cart: Cart
    items: list
    priced: object
    coupon: object
    payment_method: StorePaymentMethod | None
    invoice_kind: str
    warnings: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    unavailable: list = field(default_factory=list)

    @property
    def ready(self):
        return not self.missing

    @property
    def requires_shipping(self):
        return any(item.product.kind == Product.Kind.PHYSICAL for item in self.items)


def build_cart_view(cart, *, coupon_override=None):
    store = current_store()
    items = list(cart.items.select_related("product").order_by("added_at", "id"))
    lines = [
        PricingLine(
            key=str(item.pk),
            product_id=str(item.product_id),
            quantity=item.quantity,
            unit_price=item.product.price,
            requires_shipping=item.product.kind == Product.Kind.PHYSICAL,
        )
        for item in items
    ]
    merchandise_subtotal = sum((item.product.price * item.quantity for item in items), ZERO)
    coupon = coupon_override or cart.coupon
    evaluation = None
    if coupon is not None:
        evaluation = evaluate_coupon(
            coupon,
            subtotal=merchandise_subtotal,
            product_ids=[item.product_id for item in items],
            customer=cart.customer,
            shipping_city=(cart.shipping_address or {}).get("city"),
        )
    priced = price_cart(lines, pricing_policy(store), evaluation.discount_spec() if evaluation else None)

    warnings, unavailable = [], []
    for item in items:
        product = item.product
        if not product.is_active:
            unavailable.append(
                {
                    "item_id": str(item.pk),
                    "product_id": str(product.pk),
                    "requested": item.quantity,
                    "available": 0,
                    "reason": "discontinued",
                }
            )
            warnings.append(
                {
                    "code": ErrorCode.ITEM_UNAVAILABLE,
                    "item_id": str(item.pk),
                    "detail": f"{product.name} is no longer sold.",
                }
            )
        elif product.track_stock and item.quantity > product.stock:
            unavailable.append(
                {
                    "item_id": str(item.pk),
                    "product_id": str(product.pk),
                    "requested": item.quantity,
                    "available": product.stock,
                    "reason": "insufficient_stock",
                }
            )
            warnings.append(
                {
                    "code": ErrorCode.OUT_OF_STOCK,
                    "item_id": str(item.pk),
                    "detail": f"Only {product.stock} of {product.name} left.",
                }
            )
        if product.price != item.unit_price_seen:
            warnings.append(
                {
                    "code": "PRICE_CHANGED",
                    "item_id": str(item.pk),
                    "detail": f"{product.name} now costs {format_amount(product.price)}.",
                    "previous_price": format_amount(item.unit_price_seen),
                    "current_price": format_amount(product.price),
                }
            )
    if evaluation is not None and not evaluation.applicable:
        warnings.append(
            {
                "code": ErrorCode.COUPON_NOT_APPLICABLE,
                "detail": evaluation.problem.detail,
                "reason": str(evaluation.problem.code),
            }
        )

    payment_method = None
    if cart.payment_method:
        payment_method = StorePaymentMethod.objects.filter(method=cart.payment_method, is_enabled=True).first()

    view = CartView(
        cart=cart,
        items=items,
        priced=priced,
        coupon=evaluation,
        payment_method=payment_method,
        invoice_kind="standard" if requires_standard_invoice(cart) else "simplified",
        warnings=warnings,
        unavailable=unavailable,
    )
    if not items:
        view.missing.append("items")
    if view.requires_shipping and not cart.shipping_address:
        view.missing.append("shipping_address")
    if payment_method is None:
        view.missing.append("payment_method")
    if view.invoice_kind == "standard" and not billing_complete_for_standard_invoice(cart.billing_address):
        view.missing.append("billing_address")
    if unavailable:
        view.missing.append("available_items")
    if evaluation is not None and not evaluation.applicable:
        view.missing.append("applicable_coupon")
    return view
