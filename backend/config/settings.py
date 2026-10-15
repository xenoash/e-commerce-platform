import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost,127.0.0.1,api").split(",")
PUBLIC_API_URL = env("PUBLIC_API_URL", "http://localhost:8100")
STOREFRONT_URL = env("STOREFRONT_URL", "http://localhost:5180")
INTERNAL_API_URL = env("INTERNAL_API_URL", "http://localhost:8100")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.tenancy",
    "apps.catalog",
    "apps.customers",
    "apps.promotions",
    "apps.carts",
    "apps.orders",
    "apps.payments",
    "apps.upsell",
    "apps.invoicing",
]

MIDDLEWARE = [
    "apps.common.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.tenancy.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "55432"),
        "NAME": env("POSTGRES_DB", "ecommerce"),
        "USER": env("POSTGRES_USER", "app"),
        "PASSWORD": env("POSTGRES_PASSWORD", "app"),
        "CONN_MAX_AGE": int(env("CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "ATOMIC_REQUESTS": False,
        "TEST": {"NAME": "test_ecommerce"},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", "redis://localhost:56379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "SOCKET_CONNECT_TIMEOUT": 0.5,
            "SOCKET_TIMEOUT": 0.5,
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "ecom",
    }
}
DJANGO_REDIS_IGNORE_EXCEPTIONS = True
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = False
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.customers.authentication.CustomerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "apps.common.openapi.TenantAutoSchema",
    "EXCEPTION_HANDLER": "apps.common.errors.problem_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["apps.common.throttling.StoreRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"store": env("STORE_THROTTLE_RATE", "6000/min")},
    "UNAUTHENTICATED_USER": None,
    "COERCE_DECIMAL_TO_STRING": True,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "URL_FORMAT_OVERRIDE": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "E-commerce Platform Cart API",
    "DESCRIPTION": (
        "Multi-tenant storefront cart API. Every request names its store in the "
        "`X-Store` header. Errors are RFC 9457 problem documents with a stable `code`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "InvoiceKindEnum": ["simplified", "standard"],
        "ProductKindEnum": ["physical", "digital", "service"],
    },
    "POSTPROCESSING_HOOKS": ["drf_spectacular.hooks.postprocess_schema_enums"],
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600, "socket_connect_timeout": 2}
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.5}
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_BEAT_SCHEDULE = {
    "sweep-pending-orders": {"task": "apps.orders.tasks.sweep_pending_orders", "schedule": 120.0},
    "sweep-uninvoiced-orders": {"task": "apps.invoicing.tasks.sweep_uninvoiced_orders", "schedule": 300.0},
    "submit-due-invoices": {"task": "apps.invoicing.tasks.submit_due_invoices", "schedule": 300.0},
    "purge-idempotency-records": {"task": "apps.common.tasks.purge_idempotency_records", "schedule": 3600.0},
}

ORDER_PAYMENT_HOLD_MINUTES = int(env("ORDER_PAYMENT_HOLD_MINUTES", "15"))
IDEMPOTENCY_LEASE_SECONDS = int(env("IDEMPOTENCY_LEASE_SECONDS", "120"))
IDEMPOTENCY_RETENTION_HOURS = int(env("IDEMPOTENCY_RETENTION_HOURS", "48"))
UPSELL_TIME_BUDGET_MS = int(env("UPSELL_TIME_BUDGET_MS", "150"))
UPSELL_MAX_SUGGESTIONS = int(env("UPSELL_MAX_SUGGESTIONS", "6"))

PAYMENT_GATEWAYS = {
    "cod": "apps.payments.gateways.cod.CashOnDeliveryGateway",
    "fakepay": "apps.payments.gateways.fakepay.FakepayGateway",
    "net_terms": "apps.payments.gateways.net_terms.NetTermsGateway",
    "tap": "apps.payments.gateways.tap.TapGateway",
}
PAYMENT_GATEWAY_TIMEOUT_SECONDS = float(env("PAYMENT_GATEWAY_TIMEOUT_SECONDS", "10"))
TAP_API_BASE_URL = env("TAP_API_BASE_URL", "https://api.tap.company/v2")

UPSELL_STRATEGIES = {
    "related_products": "apps.upsell.strategies.RelatedProductsStrategy",
    "free_shipping_gap": "apps.upsell.strategies.FreeShippingGapStrategy",
    "coupon_unlock": "apps.upsell.strategies.CouponUnlockStrategy",
    "service_addons": "apps.upsell.strategies.ServiceAddonsStrategy",
}

ZATCA_MODE = env("ZATCA_MODE", "fake")
ZATCA_SIMULATION_URL = env("ZATCA_SIMULATION_URL", "https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation")
ZATCA_DEVELOPER_PORTAL_URL = env(
    "ZATCA_DEVELOPER_PORTAL_URL", "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal"
)
ZATCA_REPORTING_DEADLINE_HOURS = 24

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"context": {"()": "apps.common.logging.ContextFilter"}},
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s store=%(store)s %(message)s"}
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain", "filters": ["context"]}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
