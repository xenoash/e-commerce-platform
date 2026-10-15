from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar


class PaymentStatus(StrEnum):
    SUCCEEDED = "succeeded"
    DEFERRED = "deferred"
    REQUIRES_ACTION = "requires_action"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(frozen=True)
class GatewayContext:
    store_id: str
    store_handle: str
    method: str
    config: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentRequest:
    reference: str
    amount: Decimal
    currency: str
    method: str
    description: str
    return_url: str
    webhook_url: str
    token: str | None = None
    customer_email: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentResult:
    status: PaymentStatus
    external_ref: str = ""
    next_action: dict | None = None
    failure_code: str = ""
    failure_message: str = ""


@dataclass(frozen=True)
class RefundResult:
    succeeded: bool
    external_ref: str = ""
    failure_message: str = ""


@dataclass(frozen=True)
class WebhookEvent:
    event_id: str
    reference: str
    result: PaymentResult


class GatewayError(Exception):
    def __init__(self, message, *, transient):
        super().__init__(message)
        self.transient = transient


class InvalidSignature(Exception):
    pass


class PaymentGateway(ABC):
    key: ClassVar[str]
    supported_methods: ClassVar[frozenset[str]]
    requires_token: ClassVar[bool] = False

    def __init__(self, context: GatewayContext):
        self.context = context

    def eligibility_problem(self, customer, amount):
        return None

    def reserve_in_transaction(self, order, customer):
        return None

    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> PaymentResult: ...

    @abstractmethod
    def retrieve(self, reference: str, external_ref: str = "") -> PaymentResult: ...

    @abstractmethod
    def refund(self, reference: str, amount: Decimal) -> RefundResult: ...

    def parse_webhook(self, body: bytes, headers) -> WebhookEvent | None:
        return None
