# API guide

Base path `/api/v1`. The OpenAPI schema is in [backend/openapi.yaml](../backend/openapi.yaml) and served as Swagger UI
at `/api/v1/docs`.

## Conventions

| Topic | Rule |
|---|---|
| Tenant | Every request sends `X-Store: <store handle>`. Webhooks carry the store in the path instead. |
| Auth | `POST /auth/token` returns a bearer token that only works in the store that issued it. |
| Guest carts | `POST /carts` without a token returns a one-time `cart_token`; send it back as `X-Cart-Token`. |
| Ownership | Carts and orders are visible only to their owner. Anything else, including another store's id, is 404. |
| Money | Decimal strings with two places (`"299.00"`), plus `currency`. `prices_include_vat` says which basis prices use. |
| Writes | Every cart write returns the full cart. |
| Concurrency | Cart responses carry `ETag: "<version>"`. Send `If-Match` to make a write conditional; a stale version is 412. |
| Idempotency | `POST /carts/{id}/checkout` requires `Idempotency-Key` (8 to 255 characters). See below. |
| Pagination | Cursor based: follow `next` and `previous`; `limit` up to 100. |
| Tracing | `X-Request-Id` is echoed back, and generated when absent. |

### Status codes

| Code | Meaning |
|---|---|
| 200 / 201 | OK / created. Checkout returns 201 for a new order and 200 when it hands back an order already pending for the cart. |
| 400 | The request is malformed. `errors[]` lists every field. |
| 401 | Missing, invalid or foreign-store token. |
| 404 | Not found, or not yours. |
| 409 | Conflicts with current state: cart not open, out of stock, total changed, request in progress, resource busy. |
| 412 | `If-Match` does not match the cart version. |
| 422 | Valid request that a business rule rejects: coupon constraints, payment method not allowed, key reused with another body. |
| 428 | `Idempotency-Key` missing on checkout. |
| 429 | Store-level rate limit; honour `Retry-After`. |

### Errors

Errors are RFC 9457 problem documents (`application/problem+json`) with a stable `code`:

```json
{
  "type": "urn:ecommerce:problem:coupon-min-subtotal-not-met",
  "title": "Unprocessable content",
  "status": 422,
  "code": "COUPON_MIN_SUBTOTAL_NOT_MET",
  "detail": "Add 305.00 more to use this coupon.",
  "required": "400.00",
  "current": "95.00",
  "remaining": "305.00"
}
```

Codes, grouped:

| Group | Codes |
|---|---|
| Tenant and auth | `STORE_HEADER_MISSING`, `STORE_NOT_FOUND`, `AUTHENTICATION_REQUIRED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS` |
| Cart | `CART_NOT_FOUND`, `CART_NOT_OPEN`, `CART_VERSION_MISMATCH`, `CART_ITEM_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `QUANTITY_LIMIT_EXCEEDED`, `OUT_OF_STOCK` |
| Coupons | `COUPON_NOT_FOUND`, `COUPON_NOT_ACTIVE`, `COUPON_NOT_STARTED`, `COUPON_EXPIRED`, `COUPON_USAGE_LIMIT_REACHED`, `COUPON_CUSTOMER_LIMIT_REACHED`, `COUPON_REQUIRES_CUSTOMER`, `COUPON_MIN_SUBTOTAL_NOT_MET`, `COUPON_CITY_NOT_ELIGIBLE`, `COUPON_REQUIRES_SHIPPING_ADDRESS`, `COUPON_CUSTOMER_KIND_NOT_ELIGIBLE`, `COUPON_FIRST_ORDER_ONLY`, `COUPON_NO_ELIGIBLE_ITEMS` |
| Checkout | `CART_EMPTY`, `CART_NOT_READY`, `CART_TOTAL_CHANGED`, `ITEM_UNAVAILABLE`, `COUPON_NOT_APPLICABLE`, `PAYMENT_METHOD_NOT_AVAILABLE`, `PAYMENT_METHOD_NOT_ALLOWED`, `PAYMENT_TOKEN_REQUIRED`, `CREDIT_LIMIT_EXCEEDED` |
| Idempotency | `IDEMPOTENCY_KEY_REQUIRED`, `IDEMPOTENCY_KEY_INVALID`, `IDEMPOTENCY_KEY_REUSED`, `REQUEST_IN_PROGRESS` |
| Orders and invoices | `ORDER_NOT_FOUND`, `INVOICE_NOT_READY`, `WEBHOOK_SIGNATURE_INVALID` |
| Platform | `VALIDATION_FAILED`, `MALFORMED_REQUEST`, `RATE_LIMITED`, `RESOURCE_BUSY`, `TIMEOUT`, `INTERNAL_ERROR` |

## Checkout and idempotency

Generate one `Idempotency-Key` per checkout attempt.

- **Keep it when the outcome is unknown:** timeout, network error, 5xx, or `409 REQUEST_IN_PROGRESS`. A retry then
  replays the same order (`Idempotent-Replayed: true`) and can never charge twice.
- **Generate a new key after a definitive rejection** (4xx). Rejections that happen before an order exists free the
  key anyway, so retrying with the same key after fixing the cart also works.
- **Send `expected_total`** with the total the shopper saw. If prices moved, checkout fails with `409
  CART_TOTAL_CHANGED` and the new total, and nothing is reserved.

`GET /orders/{id}/invoice` returns the tax invoice as JSON: seller, buyer, totals, the QR payload, and line items
read back from the signed XML, so they match what was submitted to ZATCA exactly. Add `?format=xml` for the signed UBL
document. Simplified invoices are available as soon as they are issued. Standard (B2B) invoices return `409
INVOICE_NOT_READY` until ZATCA clears them.

When the response has `payment.next_action`, redirect the shopper there (3-D Secure). After the redirect back, call
`POST /orders/{id}/payment/confirm`. It asks the gateway for the result and is safe to repeat.

## Walkthrough

```bash
API=http://localhost:8100/api/v1
S='X-Store: oud-and-amber'

CART=$(curl -s -X POST $API/carts -H "$S")
ID=$(echo $CART | jq -r .id); TOKEN=$(echo $CART | jq -r .cart_token)
C="X-Cart-Token: $TOKEN"

PRODUCT=$(curl -s "$API/products?q=OUD-ROY-50" -H "$S" | jq -r '.results[0].id')
curl -s -X POST $API/carts/$ID/items -H "$S" -H "$C" -H 'Content-Type: application/json' \
  -d "{\"product_id\": \"$PRODUCT\", \"quantity\": 1}" | jq .totals

curl -s -X PUT $API/carts/$ID/coupon -H "$S" -H "$C" -H 'Content-Type: application/json' -d '{"code": "SAVE50"}' | jq .coupon

curl -s -X PUT $API/carts/$ID/shipping-address -H "$S" -H "$C" -H 'Content-Type: application/json' -d '{
  "name": "Sara Al-Harbi", "phone": "+966512345678", "street": "Tahlia Street", "building_number": "2468",
  "district": "Al Olaya", "city": "Riyadh", "postal_code": "12241"}' | jq .checkout_readiness

curl -s -X PUT $API/carts/$ID/payment-method -H "$S" -H "$C" -H 'Content-Type: application/json' -d '{"method": "card"}' \
  | jq '{ready: .checkout_readiness, total: .totals.total}'

ORDER=$(curl -s -X POST $API/carts/$ID/checkout -H "$S" -H "$C" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" -d '{"payment_token": "tok_success", "expected_total": "400.00"}')
echo $ORDER | jq '{number, status, payment: .payment.status}'

curl -s $API/orders/$(echo $ORDER | jq -r .id)/invoice -H "$S" -H "$C" | jq '{number, kind, status, icv}'
```

Sandbox tokens for `fakepay`:

| Token | Outcome |
|---|---|
| `tok_success`, `tok_applepay` | Captured |
| `tok_3ds` | Requires 3-D Secure |
| `tok_decline` | Card declined |
| `tok_insufficient_funds` | Insufficient funds |
| `tok_timeout` | Captured, but the response is lost; the sweeper reconciles it |
