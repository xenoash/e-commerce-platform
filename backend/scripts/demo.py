import argparse
import base64
import re
import sys
import uuid

import requests

B2C = "oud-and-amber"
B2B = "riyadh-office-supply"
PASSWORD = "demo-pass-123"
ADDRESS = {
    "name": "Sara Al-Harbi",
    "phone": "+966512345678",
    "email": "sara@example.com",
    "street": "Tahlia Street",
    "building_number": "2468",
    "district": "Al Olaya",
    "city": "Riyadh",
    "postal_code": "12241",
}
BILLING = {
    "name": "Khalid Al-Otaibi",
    "phone": "+966555555555",
    "street": "Olaya Street",
    "building_number": "7788",
    "district": "Al Wurud",
    "city": "Riyadh",
    "postal_code": "12251",
    "company_name": "Acme Arabia Trading Co.",
    "vat_number": "310175397400003",
    "cr_number": "1010123456",
}


class Demo:
    def __init__(self, base_url):
        self.base = base_url.rstrip("/") + "/api/v1"
        self.failures = 0

    def call(self, method, path, store, *, token=None, cart_token=None, json=None, headers=None):
        merged = {"X-Store": store, **(headers or {})}
        if token:
            merged["Authorization"] = f"Bearer {token}"
        if cart_token:
            merged["X-Cart-Token"] = cart_token
        return requests.request(method, self.base + path, json=json, headers=merged, timeout=15)

    def check(self, label, condition, detail=""):
        mark = "PASS" if condition else "FAIL"
        if not condition:
            self.failures += 1
        print(f"  [{mark}] {label}{': ' + detail if detail else ''}")

    def products(self, store):
        response = self.call("GET", "/products?limit=50", store)
        return {product["sku"]: product for product in response.json()["results"]}

    def guest_cart(self, store):
        body = self.call("POST", "/carts", store).json()
        return body["id"], body["cart_token"]

    def tenant_isolation(self):
        print("\n1. Tenant isolation")
        cart_id, cart_token = self.guest_cart(B2C)
        same = self.call("GET", f"/carts/{cart_id}", B2C, cart_token=cart_token)
        other = self.call("GET", f"/carts/{cart_id}", B2B, cart_token=cart_token)
        self.check("cart is visible in its own store", same.status_code == 200)
        self.check("same cart id is 404 from another store", other.status_code == 404, other.json().get("code", ""))
        token = self.sign_in(B2C, "sara@example.com")
        wrong_store = self.call("GET", "/me", B2B, token=token)
        self.check(
            "store A token rejected by store B", wrong_store.status_code == 401, wrong_store.json().get("code", "")
        )

    def sign_in(self, store, email):
        response = self.call("POST", "/auth/token", store, json={"email": email, "password": PASSWORD})
        return response.json()["token"]

    def coupon_and_3ds_checkout(self):
        print("\n2. Guest checkout: coupon constraint, upsell, 3-D Secure, ZATCA simplified invoice")
        products = self.products(B2C)
        cart_id, cart_token = self.guest_cart(B2C)

        def add(sku, quantity=1):
            payload = {"product_id": products[sku]["id"], "quantity": quantity}
            return self.call("POST", f"/carts/{cart_id}/items", B2C, cart_token=cart_token, json=payload)

        add("MSK-THR-30")
        rejected = self.call("PUT", f"/carts/{cart_id}/coupon", B2C, cart_token=cart_token, json={"code": "SAVE50"})
        self.check(
            "SAVE50 rejected below its minimum",
            rejected.status_code == 422 and rejected.json()["code"] == "COUPON_MIN_SUBTOTAL_NOT_MET",
            f"remaining {rejected.json().get('remaining')}",
        )
        suggestions = self.call("GET", f"/carts/{cart_id}/suggestions", B2C, cart_token=cart_token).json()[
            "suggestions"
        ]
        self.check("upsell suggests something", bool(suggestions), "; ".join(s["headline"] for s in suggestions[:3]))
        add("OUD-ROY-50")
        applied = self.call("PUT", f"/carts/{cart_id}/coupon", B2C, cart_token=cart_token, json={"code": "SAVE50"})
        self.check(
            "SAVE50 accepted once the minimum is met",
            applied.status_code == 200,
            f"discount {applied.json()['totals']['discount']}",
        )
        version = applied.headers["ETag"]
        stale = self.call(
            "PUT",
            f"/carts/{cart_id}/shipping-address",
            B2C,
            cart_token=cart_token,
            json=ADDRESS,
            headers={"If-Match": '"1"'},
        )
        self.check("stale If-Match is refused", stale.status_code == 412, stale.json().get("code", ""))
        self.call(
            "PUT",
            f"/carts/{cart_id}/shipping-address",
            B2C,
            cart_token=cart_token,
            json=ADDRESS,
            headers={"If-Match": version},
        )
        cart = self.call(
            "PUT", f"/carts/{cart_id}/payment-method", B2C, cart_token=cart_token, json={"method": "card"}
        ).json()
        self.check(
            "cart is ready to check out", cart["checkout_readiness"]["ready"], f"total {cart['totals']['total']}"
        )

        key = str(uuid.uuid4())
        body = {"payment_token": "tok_3ds", "expected_total": cart["totals"]["total"]}
        first = self.call(
            "POST",
            f"/carts/{cart_id}/checkout",
            B2C,
            cart_token=cart_token,
            json=body,
            headers={"Idempotency-Key": key},
        )
        order = first.json()
        self.check(
            "checkout returns 201 with a 3-D Secure redirect",
            first.status_code == 201 and order["payment"]["next_action"] is not None,
        )
        replay = self.call(
            "POST",
            f"/carts/{cart_id}/checkout",
            B2C,
            cart_token=cart_token,
            json=body,
            headers={"Idempotency-Key": key},
        )
        self.check(
            "retrying with the same Idempotency-Key replays the same order",
            replay.json()["id"] == order["id"] and replay.headers.get("Idempotent-Replayed") == "true",
        )
        challenge = order["payment"]["next_action"]["url"]
        requests.post(challenge, data={"outcome": "approve"}, allow_redirects=False, timeout=15)
        confirmed = self.call("POST", f"/orders/{order['id']}/payment/confirm", B2C, cart_token=cart_token).json()
        self.check("payment confirmed after 3-D Secure", confirmed["status"] == "paid", confirmed["number"])
        invoice = self.call("GET", f"/orders/{order['id']}/invoice", B2C, cart_token=cart_token)
        payload = invoice.json()
        self.check(
            "simplified tax invoice issued and reported", payload.get("status") == "reported", payload.get("number", "")
        )
        if invoice.status_code == 200:
            fields = decode_tlv(payload["qr_code"])
            self.check(
                "QR carries seller VAT, total and VAT",
                fields[2] == b"399999999900003" and fields[4].decode() == confirmed["totals"]["total"],
                f"tags {sorted(fields)}",
            )

    def decline_releases_stock(self):
        print("\n3. Declined card releases stock and reopens the cart")
        products = self.products(B2C)
        before = products["ROS-TAF-50"]["stock_level"]
        cart_id, cart_token = self.guest_cart(B2C)
        self.call(
            "POST",
            f"/carts/{cart_id}/items",
            B2C,
            cart_token=cart_token,
            json={"product_id": products["ROS-TAF-50"]["id"], "quantity": 2},
        )
        self.call("PUT", f"/carts/{cart_id}/shipping-address", B2C, cart_token=cart_token, json=ADDRESS)
        self.call("PUT", f"/carts/{cart_id}/payment-method", B2C, cart_token=cart_token, json={"method": "card"})
        order = self.call(
            "POST",
            f"/carts/{cart_id}/checkout",
            B2C,
            cart_token=cart_token,
            json={"payment_token": "tok_decline"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        ).json()
        after = self.products(B2C)["ROS-TAF-50"]["stock_level"]
        cart = self.call("GET", f"/carts/{cart_id}", B2C, cart_token=cart_token).json()
        self.check("order marked payment_failed", order["status"] == "payment_failed", order["payment"]["failure_code"])
        self.check("stock restored", before == after, f"{before} -> {after}")
        self.check("cart reopened for another attempt", cart["status"] == "open")

    def b2b_net_terms(self):
        print("\n4. B2B: business account, pay on invoice, standard invoice cleared by ZATCA")
        token = self.sign_in(B2B, "procurement@acme.example.com")
        products = self.products(B2B)
        cart = self.call("POST", "/carts", B2B, token=token).json()
        cart_id = cart["id"]
        self.call(
            "POST",
            f"/carts/{cart_id}/items",
            B2B,
            token=token,
            json={"product_id": products["CHR-ERG"]["id"], "quantity": 3},
        )
        self.call(
            "POST",
            f"/carts/{cart_id}/items",
            B2B,
            token=token,
            json={"product_id": products["SVC-INSTALL"]["id"], "quantity": 1},
        )
        coupon = self.call("PUT", f"/carts/{cart_id}/coupon", B2B, token=token, json={"code": "BULK5"})
        self.check(
            "business-only coupon accepted",
            coupon.status_code == 200,
            f"discount {coupon.json()['totals']['discount']}",
        )
        self.call(
            "PUT",
            f"/carts/{cart_id}/shipping-address",
            B2B,
            token=token,
            json={**ADDRESS, "name": "Acme Riyadh Office"},
        )
        not_ready = self.call("GET", f"/carts/{cart_id}", B2B, token=token).json()
        self.check(
            "standard invoice needs billing details", "billing_address" in not_ready["checkout_readiness"]["missing"]
        )
        self.call("PUT", f"/carts/{cart_id}/billing-address", B2B, token=token, json=BILLING)
        cart = self.call(
            "PUT", f"/carts/{cart_id}/payment-method", B2B, token=token, json={"method": "net_terms"}
        ).json()
        self.check(
            "prices shown ex-VAT with VAT on top",
            cart["totals"]["prices_include_vat"] is False,
            f"net {cart['totals']['taxable_amount']} + VAT {cart['totals']['vat']}",
        )
        order = self.call(
            "POST",
            f"/carts/{cart_id}/checkout",
            B2B,
            token=token,
            json={"po_number": "PO-2026-0042"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        ).json()
        self.check("order confirmed on net terms", order["status"] == "confirmed", order["number"])
        invoice = self.call("GET", f"/orders/{order['id']}/invoice", B2B, token=token).json()
        self.check(
            "standard invoice cleared",
            invoice.get("status") == "cleared" and invoice.get("kind") == "standard",
            invoice.get("number", ""),
        )
        xml = self.call("GET", f"/orders/{order['id']}/invoice?format=xml", B2B, token=token).text
        self.check("XML carries the buyer VAT and PO number", "310175397400003" in xml and "PO-2026-0042" in xml)
        self.check("XML is a 0100000 standard invoice", re.search(r'InvoiceTypeCode name="0100000"', xml) is not None)

    def run(self):
        self.tenant_isolation()
        self.coupon_and_3ds_checkout()
        self.decline_releases_stock()
        self.b2b_net_terms()
        print(f"\n{'All checks passed.' if not self.failures else f'{self.failures} check(s) failed.'}")
        return self.failures


def decode_tlv(encoded):
    raw = base64.b64decode(encoded)
    fields, position = {}, 0
    while position < len(raw):
        tag, length = raw[position], raw[position + 1]
        fields[tag] = raw[position + 2 : position + 2 + length]
        position += 2 + length
    return fields


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Walk the cart API end to end against a running stack.")
    parser.add_argument("--base-url", default="http://localhost:8100")
    sys.exit(1 if Demo(parser.parse_args().base_url).run() else 0)
