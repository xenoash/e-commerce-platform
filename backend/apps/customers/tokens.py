import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from .models import AccessToken

TOKEN_PREFIX = "cst_"
TOKEN_LIFETIME = timedelta(days=30)


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(customer):
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token = AccessToken.objects.create(
        customer=customer, key_hash=hash_token(raw), expires_at=timezone.now() + TOKEN_LIFETIME
    )
    return raw, token


def authenticate_token(raw):
    if not raw.startswith(TOKEN_PREFIX):
        return None
    return (
        AccessToken.objects.select_related("customer")
        .filter(key_hash=hash_token(raw), expires_at__gt=timezone.now())
        .first()
    )
