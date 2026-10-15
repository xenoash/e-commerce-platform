from decimal import Decimal

from django.db.models import Sum

from apps.common.errors import ErrorCode, Problem
from apps.common.money import format_amount

from ..base import PaymentGateway, PaymentResult, PaymentStatus, RefundResult


class NetTermsGateway(PaymentGateway):
    key = "net_terms"
    supported_methods = frozenset({"net_terms"})

    def eligibility_problem(self, customer, amount):
        if customer is None or not customer.is_business or not customer.credit_approved:
            return Problem(
                422,
                ErrorCode.PAYMENT_METHOD_NOT_ALLOWED,
                "Pay on invoice is available to approved business accounts.",
            )
        return None

    def reserve_in_transaction(self, order, customer):
        from apps.customers.models import Customer
        from apps.payments.models import Payment

        locked = Customer.objects.select_for_update().get(pk=customer.pk)
        outstanding = Payment.objects.filter(
            order__customer=locked,
            gateway=self.key,
            status__in=[Payment.Status.INITIATED, Payment.Status.DEFERRED],
        ).exclude(order=order).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        available = locked.credit_limit - outstanding
        if order.total > available:
            raise Problem(
                409,
                ErrorCode.CREDIT_LIMIT_EXCEEDED,
                "This order is above the account's available credit.",
                credit_limit=format_amount(locked.credit_limit),
                outstanding=format_amount(outstanding),
                available=format_amount(max(available, Decimal("0.00"))),
            )

    def create_payment(self, request):
        return PaymentResult(PaymentStatus.DEFERRED, external_ref=f"terms_{request.reference}")

    def retrieve(self, reference, external_ref=""):
        return PaymentResult(PaymentStatus.DEFERRED, external_ref=f"terms_{reference}")

    def refund(self, reference, amount):
        return RefundResult(succeeded=True, external_ref=f"terms_credit_{reference}")
