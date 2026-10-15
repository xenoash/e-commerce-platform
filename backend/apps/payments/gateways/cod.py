from decimal import Decimal

from apps.common.errors import ErrorCode, Problem

from ..base import PaymentGateway, PaymentResult, PaymentStatus, RefundResult


class CashOnDeliveryGateway(PaymentGateway):
    key = "cod"
    supported_methods = frozenset({"cod"})

    def eligibility_problem(self, customer, amount):
        limit = self.context.config.get("max_amount")
        if limit is not None and amount > Decimal(str(limit)):
            return Problem(
                422,
                ErrorCode.PAYMENT_METHOD_NOT_ALLOWED,
                f"Cash on delivery is available for orders up to {limit}.",
                max_amount=str(limit),
            )
        return None

    def create_payment(self, request):
        return PaymentResult(PaymentStatus.DEFERRED, external_ref=f"cod_{request.reference}")

    def retrieve(self, reference, external_ref=""):
        return PaymentResult(PaymentStatus.DEFERRED, external_ref=f"cod_{reference}")

    def refund(self, reference, amount):
        return RefundResult(succeeded=True, external_ref=f"cod_refund_{reference}")
