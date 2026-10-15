import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .errors import ErrorCode, Problem
from .models import IdempotencyRecord

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_\-:.]{8,255}$")


class ClaimState(StrEnum):
    NEW = "new"
    REPLAY = "replay"


@dataclass
class Claim:
    state: ClaimState
    record: IdempotencyRecord


def require_key(request):
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise Problem(428, ErrorCode.IDEMPOTENCY_KEY_REQUIRED, "Send a unique Idempotency-Key header for this request.")
    if not KEY_PATTERN.match(key):
        raise Problem(
            400, ErrorCode.IDEMPOTENCY_KEY_INVALID, "Idempotency-Key must be 8-255 characters of [A-Za-z0-9_-:.]."
        )
    return key


def fingerprint(*parts):
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def claim(*, scope, resource_id, key, request_fingerprint):
    now = timezone.now()
    lease_until = now + timedelta(seconds=settings.IDEMPOTENCY_LEASE_SECONDS)
    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                scope=scope,
                resource_id=str(resource_id),
                key=key,
                fingerprint=request_fingerprint,
                locked_until=lease_until,
            )
        return Claim(ClaimState.NEW, record)
    except IntegrityError:
        record = IdempotencyRecord.objects.get(scope=scope, resource_id=str(resource_id), key=key)
    if record.fingerprint != request_fingerprint:
        raise Problem(
            422,
            ErrorCode.IDEMPOTENCY_KEY_REUSED,
            "This Idempotency-Key was already used with a different request body.",
        )
    if record.status == IdempotencyRecord.Status.COMPLETED:
        return Claim(ClaimState.REPLAY, record)
    taken_over = IdempotencyRecord.objects.filter(
        pk=record.pk, status=IdempotencyRecord.Status.IN_PROGRESS, locked_until__lt=now
    ).update(locked_until=lease_until)
    if taken_over:
        record.refresh_from_db()
        return Claim(ClaimState.NEW, record)
    raise Problem(
        409,
        ErrorCode.REQUEST_IN_PROGRESS,
        "A request with this Idempotency-Key is still being processed.",
        headers={"Retry-After": "2"},
    )


def release(record):
    IdempotencyRecord.objects.filter(pk=record.pk, status=IdempotencyRecord.Status.IN_PROGRESS).delete()


def attach_order(record, order_id):
    IdempotencyRecord.objects.filter(pk=record.pk).update(order_id=order_id)
    record.order_id = order_id


def complete(record, *, response_status, order_id):
    IdempotencyRecord.objects.filter(pk=record.pk).update(
        status=IdempotencyRecord.Status.COMPLETED, response_status=response_status, order_id=order_id
    )
