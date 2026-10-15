import logging
from enum import StrEnum

from django.db import OperationalError
from django.http import Http404, JsonResponse
from psycopg import errors as pg_errors
from rest_framework import exceptions, status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"


class ErrorCode(StrEnum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    NOT_ACCEPTABLE = "NOT_ACCEPTABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_TOKEN = "INVALID_TOKEN"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    RESOURCE_BUSY = "RESOURCE_BUSY"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    STORE_HEADER_MISSING = "STORE_HEADER_MISSING"
    STORE_NOT_FOUND = "STORE_NOT_FOUND"
    CART_NOT_FOUND = "CART_NOT_FOUND"
    CART_NOT_OPEN = "CART_NOT_OPEN"
    CART_VERSION_MISMATCH = "CART_VERSION_MISMATCH"
    CART_EMPTY = "CART_EMPTY"
    CART_NOT_READY = "CART_NOT_READY"
    CART_TOTAL_CHANGED = "CART_TOTAL_CHANGED"
    CART_ITEM_NOT_FOUND = "CART_ITEM_NOT_FOUND"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    ITEM_UNAVAILABLE = "ITEM_UNAVAILABLE"
    QUANTITY_LIMIT_EXCEEDED = "QUANTITY_LIMIT_EXCEEDED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    COUPON_NOT_FOUND = "COUPON_NOT_FOUND"
    COUPON_NOT_ACTIVE = "COUPON_NOT_ACTIVE"
    COUPON_EXPIRED = "COUPON_EXPIRED"
    COUPON_NOT_STARTED = "COUPON_NOT_STARTED"
    COUPON_USAGE_LIMIT_REACHED = "COUPON_USAGE_LIMIT_REACHED"
    COUPON_CUSTOMER_LIMIT_REACHED = "COUPON_CUSTOMER_LIMIT_REACHED"
    COUPON_REQUIRES_CUSTOMER = "COUPON_REQUIRES_CUSTOMER"
    COUPON_MIN_SUBTOTAL_NOT_MET = "COUPON_MIN_SUBTOTAL_NOT_MET"
    COUPON_CITY_NOT_ELIGIBLE = "COUPON_CITY_NOT_ELIGIBLE"
    COUPON_REQUIRES_SHIPPING_ADDRESS = "COUPON_REQUIRES_SHIPPING_ADDRESS"
    COUPON_CUSTOMER_KIND_NOT_ELIGIBLE = "COUPON_CUSTOMER_KIND_NOT_ELIGIBLE"
    COUPON_FIRST_ORDER_ONLY = "COUPON_FIRST_ORDER_ONLY"
    COUPON_NO_ELIGIBLE_ITEMS = "COUPON_NO_ELIGIBLE_ITEMS"
    COUPON_NOT_APPLICABLE = "COUPON_NOT_APPLICABLE"
    NO_COUPON_APPLIED = "NO_COUPON_APPLIED"
    PAYMENT_METHOD_NOT_AVAILABLE = "PAYMENT_METHOD_NOT_AVAILABLE"
    PAYMENT_METHOD_NOT_ALLOWED = "PAYMENT_METHOD_NOT_ALLOWED"
    PAYMENT_TOKEN_REQUIRED = "PAYMENT_TOKEN_REQUIRED"
    CREDIT_LIMIT_EXCEEDED = "CREDIT_LIMIT_EXCEEDED"
    BUYER_DETAILS_REQUIRED = "BUYER_DETAILS_REQUIRED"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    IDEMPOTENCY_KEY_INVALID = "IDEMPOTENCY_KEY_INVALID"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    REQUEST_IN_PROGRESS = "REQUEST_IN_PROGRESS"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    PAYMENT_NOT_PENDING = "PAYMENT_NOT_PENDING"
    INVOICE_NOT_READY = "INVOICE_NOT_READY"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"
    GATEWAY_NOT_FOUND = "GATEWAY_NOT_FOUND"


TITLES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    406: "Not acceptable",
    409: "Conflict",
    412: "Precondition failed",
    415: "Unsupported media type",
    422: "Unprocessable content",
    428: "Precondition required",
    429: "Too many requests",
    500: "Internal server error",
    503: "Service unavailable",
}


class Problem(Exception):
    def __init__(self, status_code, code, detail=None, *, headers=None, **extra):
        super().__init__(detail or code)
        self.status_code = status_code
        self.code = ErrorCode(code)
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra

    def as_dict(self):
        body = {
            "type": f"urn:ecommerce:problem:{self.code.lower().replace('_', '-')}",
            "title": TITLES.get(self.status_code, "Error"),
            "status": self.status_code,
            "code": str(self.code),
        }
        if self.detail:
            body["detail"] = self.detail
        body.update(self.extra)
        return body


def problem_response(problem: Problem) -> Response:
    return Response(
        problem.as_dict(),
        status=problem.status_code,
        headers=problem.headers,
        content_type=PROBLEM_CONTENT_TYPE,
    )


def problem_json_response(problem: Problem) -> JsonResponse:
    response = JsonResponse(problem.as_dict(), status=problem.status_code, content_type=PROBLEM_CONTENT_TYPE)
    for name, value in problem.headers.items():
        response[name] = value
    return response


def _flatten_validation_errors(detail, prefix=""):
    if isinstance(detail, dict):
        for key, value in detail.items():
            name = key if key != "non_field_errors" else ""
            path = f"{prefix}.{name}" if prefix and name else (name or prefix)
            yield from _flatten_validation_errors(value, path)
    elif isinstance(detail, list):
        if all(isinstance(item, exceptions.ErrorDetail | str) for item in detail):
            for item in detail:
                yield {"field": prefix or None, "code": getattr(item, "code", "invalid"), "message": str(item)}
        else:
            for index, item in enumerate(detail):
                yield from _flatten_validation_errors(item, f"{prefix}[{index}]")
    else:
        yield {"field": prefix or None, "code": getattr(detail, "code", "invalid"), "message": str(detail)}


def _translate(exc) -> Problem | None:
    if isinstance(exc, Problem):
        return exc
    if isinstance(exc, Http404):
        return Problem(404, ErrorCode.NOT_FOUND, "The requested resource does not exist.")
    if isinstance(exc, exceptions.ValidationError):
        return Problem(
            400,
            ErrorCode.VALIDATION_FAILED,
            "The request body is invalid.",
            errors=list(_flatten_validation_errors(exc.detail)),
        )
    if isinstance(exc, exceptions.ParseError):
        return Problem(400, ErrorCode.MALFORMED_REQUEST, str(exc.detail))
    if isinstance(exc, exceptions.AuthenticationFailed):
        return Problem(401, ErrorCode.INVALID_TOKEN, str(exc.detail), headers={"WWW-Authenticate": "Bearer"})
    if isinstance(exc, exceptions.NotAuthenticated):
        return Problem(401, ErrorCode.AUTHENTICATION_REQUIRED, str(exc.detail), headers={"WWW-Authenticate": "Bearer"})
    if isinstance(exc, exceptions.PermissionDenied):
        return Problem(403, ErrorCode.PERMISSION_DENIED, str(exc.detail))
    if isinstance(exc, exceptions.NotFound):
        return Problem(404, ErrorCode.NOT_FOUND, str(exc.detail))
    if isinstance(exc, exceptions.MethodNotAllowed):
        return Problem(405, ErrorCode.METHOD_NOT_ALLOWED, str(exc.detail))
    if isinstance(exc, exceptions.NotAcceptable):
        return Problem(406, ErrorCode.NOT_ACCEPTABLE, str(exc.detail))
    if isinstance(exc, exceptions.UnsupportedMediaType):
        return Problem(415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, str(exc.detail))
    if isinstance(exc, exceptions.Throttled):
        wait = int(exc.wait or 1)
        return Problem(
            429, ErrorCode.RATE_LIMITED, "Too many requests for this store.", headers={"Retry-After": str(wait)}
        )
    if isinstance(exc, OperationalError):
        cause = exc.__cause__
        if isinstance(cause, pg_errors.LockNotAvailable):
            return Problem(
                409,
                ErrorCode.RESOURCE_BUSY,
                "Another request is updating this resource. Retry shortly.",
                headers={"Retry-After": "1"},
            )
        if isinstance(cause, pg_errors.QueryCanceled):
            return Problem(503, ErrorCode.TIMEOUT, "The request took too long.", headers={"Retry-After": "2"})
    if isinstance(exc, exceptions.APIException):
        return Problem(exc.status_code, ErrorCode.MALFORMED_REQUEST, str(exc.detail))
    return None


def problem_exception_handler(exc, context):
    problem = _translate(exc)
    if problem is None:
        logger.exception("unhandled_error", exc_info=exc)
        problem = Problem(500, ErrorCode.INTERNAL_ERROR, "Something went wrong on our side.")
    return problem_response(problem)


def not_found(code=ErrorCode.NOT_FOUND, detail=None):
    return Problem(status.HTTP_404_NOT_FOUND, code, detail or "The requested resource does not exist.")
