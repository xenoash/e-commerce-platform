from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions

from apps.tenancy.context import current_store_or_none

from .tokens import authenticate_token


class CustomerTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("latin-1")
        if not header:
            return None
        scheme, _, raw = header.partition(" ")
        if scheme != self.keyword or not raw.strip():
            raise exceptions.AuthenticationFailed("Use 'Authorization: Bearer <token>'.")
        if current_store_or_none() is None:
            raise exceptions.AuthenticationFailed("Customer tokens are only valid on store endpoints.")
        token = authenticate_token(raw.strip())
        if token is None:
            raise exceptions.AuthenticationFailed("The token is invalid, expired, or belongs to another store.")
        return token.customer, token

    def authenticate_header(self, request):
        return self.keyword


class CustomerTokenScheme(OpenApiAuthenticationExtension):
    target_class = CustomerTokenAuthentication
    name = "customerToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": "Store-scoped customer token from POST /api/v1/auth/token.",
        }
