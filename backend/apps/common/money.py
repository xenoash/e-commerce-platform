from collections.abc import Sequence
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def to_money(value) -> Decimal:
    if isinstance(value, float):
        value = repr(value)
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def vat_for_net(net: Decimal, rate_percent: Decimal) -> Decimal:
    return to_money(net * rate_percent / HUNDRED)


def net_from_gross(gross: Decimal, rate_percent: Decimal) -> Decimal:
    if not rate_percent:
        return to_money(gross)
    return to_money(gross / (1 + rate_percent / HUNDRED))


def allocate(total: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    if not weights:
        return []
    total = to_money(total)
    weight_sum = sum(weights, Decimal(0))
    if weight_sum == 0:
        weights = [Decimal(1)] * len(weights)
        weight_sum = Decimal(len(weights))
    exact = [total * w / weight_sum for w in weights]
    shares = [value.quantize(CENT, rounding=ROUND_DOWN) for value in exact]
    leftover = int(((total - sum(shares, ZERO)) / CENT).to_integral_value())
    by_remainder = sorted(range(len(weights)), key=lambda i: (exact[i] - shares[i], -i), reverse=True)
    step = CENT if leftover >= 0 else -CENT
    for index in by_remainder[: abs(leftover)]:
        shares[index] += step
    return shares


def format_amount(value: Decimal) -> str:
    return f"{to_money(value):.2f}"
