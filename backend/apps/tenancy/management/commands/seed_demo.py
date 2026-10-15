from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from apps.catalog.models import Product, ProductRecommendation
from apps.customers.models import Customer
from apps.invoicing.models import EgsDevice
from apps.invoicing.zatca.crypto import certificate_b64, generate_private_key, private_key_pem, self_signed_certificate
from apps.payments.models import StorePaymentMethod
from apps.promotions.models import Coupon
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Store
from apps.tenancy.resolver import forget_store

DEMO_PASSWORD = "demo-pass-123"

STORES = [
    {
        "store": {
            "handle": "oud-and-amber",
            "name": "Oud & Amber",
            "legal_name": "Oud and Amber Trading Company",
            "vat_number": "399999999900003",
            "cr_number": "1010010000",
            "street": "King Fahd Road",
            "building_number": "1234",
            "district": "Al Olaya",
            "city": "Riyadh",
            "postal_code": "12211",
            "prices_include_vat": True,
            "shipping_fee": Decimal("25.00"),
            "free_shipping_threshold": Decimal("300.00"),
            "upsell_config": [
                {"strategy": "related_products", "config": {"limit": 3}},
                {"strategy": "free_shipping_gap", "config": {"limit": 2}},
                {"strategy": "coupon_unlock"},
                {"strategy": "service_addons", "config": {"limit": 1}},
            ],
        },
        "products": [
            ("OUD-ROY-50", "Oud Royale 50ml", "physical", "450.00", 40, False),
            ("AMB-NGT-100", "Amber Nights 100ml", "physical", "320.00", 25, False),
            ("MSK-THR-30", "Musk Tahara 30ml", "physical", "95.00", 3, False),
            ("ROS-TAF-50", "Taif Rose 50ml", "physical", "280.00", 18, False),
            ("BKH-BOX", "Bakhoor Incense Box", "physical", "60.00", 60, False),
            ("ATM-TRV", "Travel Atomizer", "physical", "35.00", 100, False),
            ("OUD-LTD-1", "Limited Edition Oud", "physical", "1200.00", 1, False),
            ("GIFT-WRAP", "Gift Wrapping", "service", "15.00", None, True),
        ],
        "recommendations": [
            ("OUD-ROY-50", "BKH-BOX", "Pairs with Oud Royale"),
            ("OUD-ROY-50", "ATM-TRV", "Carry it with you"),
            ("AMB-NGT-100", "ATM-TRV", "Carry it with you"),
            ("ROS-TAF-50", "MSK-THR-30", "Layer it with musk"),
        ],
        "coupons": [
            {
                "code": "WELCOME10",
                "kind": "percent",
                "value": "10",
                "description": "10% off your first order",
                "rules": [{"type": "first_order_only"}],
            },
            {
                "code": "SAVE50",
                "kind": "fixed",
                "value": "50",
                "description": "50 off orders over 400",
                "advertise": True,
                "rules": [{"type": "min_subtotal", "amount": "400.00"}],
            },
            {
                "code": "RIYADH15",
                "kind": "percent",
                "value": "15",
                "max_discount": "100",
                "description": "15% off deliveries in Riyadh",
                "rules": [{"type": "allowed_cities", "cities": ["Riyadh"]}],
            },
            {"code": "FREESHIP", "kind": "free_shipping", "value": "0", "description": "Free delivery"},
            {"code": "FLASH1", "kind": "fixed", "value": "20", "description": "One lucky shopper", "usage_limit": 1},
        ],
        "payment_methods": [
            ("card", "fakepay", "Credit or debit card", {}),
            ("apple_pay", "fakepay", "Apple Pay", {}),
            ("cod", "cod", "Cash on delivery", {"max_amount": "1000.00"}),
        ],
        "customers": [
            {"email": "sara@example.com", "name": "Sara Al-Harbi", "kind": "individual", "phone": "+966512345678"},
        ],
    },
    {
        "store": {
            "handle": "riyadh-office-supply",
            "name": "Riyadh Office Supply",
            "legal_name": "Riyadh Office Supply Company",
            "vat_number": "399999999800003",
            "cr_number": "1010020000",
            "street": "Prince Sultan Street",
            "building_number": "4321",
            "district": "Al Malqa",
            "city": "Riyadh",
            "postal_code": "13521",
            "prices_include_vat": False,
            "shipping_fee": Decimal("40.00"),
            "free_shipping_threshold": Decimal("1000.00"),
            "b2b_enabled": True,
            "upsell_config": [
                {"strategy": "related_products"},
                {"strategy": "free_shipping_gap"},
                {"strategy": "coupon_unlock"},
            ],
        },
        "products": [
            ("PAP-A4-5", "A4 Paper, 5 reams", "physical", "95.00", 500, False),
            ("CHR-ERG", "Ergonomic Office Chair", "physical", "850.00", 30, False),
            ("TNR-BLK", "Black Toner Cartridge", "physical", "310.00", 80, False),
            ("WBD-120", "Whiteboard 120cm", "physical", "220.00", 15, False),
            ("SVC-INSTALL", "Furniture Installation", "service", "150.00", None, False),
        ],
        "recommendations": [
            ("CHR-ERG", "SVC-INSTALL", "Have it assembled on site"),
            ("TNR-BLK", "PAP-A4-5", "Restock paper too"),
        ],
        "coupons": [
            {
                "code": "BULK5",
                "kind": "percent",
                "value": "5",
                "description": "5% off business orders over 2,000",
                "advertise": True,
                "rules": [
                    {"type": "customer_kind", "kinds": ["business"]},
                    {"type": "min_subtotal", "amount": "2000.00"},
                ],
            },
        ],
        "payment_methods": [
            ("card", "fakepay", "Corporate card", {}),
            ("net_terms", "net_terms", "Pay on invoice (net 30)", {}),
        ],
        "customers": [
            {
                "email": "procurement@acme.example.com",
                "name": "Khalid Al-Otaibi",
                "kind": "business",
                "company_name": "Acme Arabia Trading Co.",
                "vat_number": "310175397400003",
                "cr_number": "1010123456",
                "credit_approved": True,
                "credit_limit": Decimal("20000.00"),
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Create two demo stores with catalogue, coupons, payment methods, customers and e-invoicing devices."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all data first.")

    def handle(self, *args, reset=False, **options):
        if reset:
            self._truncate()
        for spec in STORES:
            handle = spec["store"]["handle"]
            if Store.objects.filter(handle=handle).exists():
                self.stdout.write(f"{handle}: already seeded")
                continue
            with transaction.atomic():
                self._seed(spec)
            self.stdout.write(self.style.SUCCESS(f"{handle}: seeded"))
        self.stdout.write(f"Demo customer password: {DEMO_PASSWORD}")

    def _truncate(self):
        tables = connection.introspection.django_table_names(only_existing=True)
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
        for spec in STORES:
            forget_store(spec["store"]["handle"])

    def _seed(self, spec):
        store = Store(**spec["store"])
        store.full_clean()
        store.save()
        with tenant_context(store):
            products = {}
            for sku, name, kind, price, stock, is_addon in spec["products"]:
                products[sku] = Product.objects.create(
                    sku=sku,
                    name=name,
                    kind=kind,
                    price=Decimal(price),
                    track_stock=stock is not None,
                    stock=stock or 0,
                    is_addon=is_addon,
                    description=f"{name} from {store.name}.",
                )
            for position, (source, target, headline) in enumerate(spec["recommendations"]):
                ProductRecommendation.objects.create(
                    product=products[source], recommended=products[target], position=position, headline=headline
                )
            for coupon in spec["coupons"]:
                Coupon.objects.create(**{**coupon, "value": Decimal(coupon["value"])})
            for position, (method, gateway, display_name, config) in enumerate(spec["payment_methods"]):
                StorePaymentMethod.objects.create(
                    method=method, gateway=gateway, display_name=display_name, config=config, position=position
                )
            for data in spec["customers"]:
                customer = Customer(**data)
                customer.set_password(DEMO_PASSWORD)
                customer.save()
            key = generate_private_key()
            certificate = self_signed_certificate(
                key, common_name=f"EGS-{store.handle}", organization=store.legal_name, vat_number=store.vat_number
            )
            EgsDevice.objects.create(
                name="Web checkout",
                serial_number=f"1-EcommercePlatform|2-1.0|3-{store.pk}",
                private_key_pem=private_key_pem(key),
                certificate_b64=certificate_b64(certificate),
            )
