from dataclasses import dataclass
from decimal import Decimal

from apps.common.money import HUNDRED, ZERO, allocate, net_from_gross, to_money, vat_for_net


@dataclass(frozen=True)
class PricingLine:
    key: str
    product_id: str
    quantity: int
    unit_price: Decimal
    requires_shipping: bool = True


@dataclass(frozen=True)
class DiscountSpec:
    kind: str
    value: Decimal
    max_discount: Decimal | None = None
    eligible_product_ids: frozenset[str] | None = None


@dataclass(frozen=True)
class PricingPolicy:
    prices_include_vat: bool
    vat_rate: Decimal
    shipping_fee: Decimal
    free_shipping_threshold: Decimal | None = None


@dataclass(frozen=True)
class PricedComponent:
    key: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    discount: Decimal
    net: Decimal
    vat: Decimal
    total: Decimal


@dataclass(frozen=True)
class PricedCart:
    lines: tuple[PricedComponent, ...]
    shipping: PricedComponent
    prices_include_vat: bool
    vat_rate: Decimal
    subtotal: Decimal
    eligible_subtotal: Decimal
    item_discount: Decimal
    shipping_discount: Decimal
    taxable_amount: Decimal
    vat: Decimal
    total: Decimal

    @property
    def discount(self):
        return self.item_discount + self.shipping_discount

    @property
    def shipping_fee(self):
        return self.shipping.subtotal

    def line(self, key):
        return next(line for line in self.lines if line.key == key)


SHIPPING_KEY = "shipping"


def _item_discount(spec, eligible_subtotal):
    if spec is None or eligible_subtotal <= ZERO:
        return ZERO
    if spec.kind == "percent":
        amount = to_money(eligible_subtotal * spec.value / HUNDRED)
        if spec.max_discount is not None:
            amount = min(amount, spec.max_discount)
        return min(amount, eligible_subtotal)
    if spec.kind == "fixed":
        return min(to_money(spec.value), eligible_subtotal)
    return ZERO


def _is_eligible(line, spec):
    return spec is not None and (spec.eligible_product_ids is None or line.product_id in spec.eligible_product_ids)


def price_cart(lines, policy, discount=None):
    subtotals = [to_money(line.unit_price * line.quantity) for line in lines]
    subtotal = sum(subtotals, ZERO)
    eligible_indexes = [i for i, line in enumerate(lines) if _is_eligible(line, discount)]
    eligible_subtotal = sum((subtotals[i] for i in eligible_indexes), ZERO)

    item_discount = _item_discount(discount, eligible_subtotal)
    line_discounts = [ZERO] * len(lines)
    shares = allocate(item_discount, [subtotals[i] for i in eligible_indexes])
    for index, share in zip(eligible_indexes, shares, strict=True):
        line_discounts[index] = share

    needs_shipping = any(line.requires_shipping for line in lines)
    shipping_fee = to_money(policy.shipping_fee) if needs_shipping else ZERO
    merchandise_after_discount = subtotal - item_discount
    if policy.free_shipping_threshold is not None and merchandise_after_discount >= policy.free_shipping_threshold:
        shipping_fee = ZERO
    shipping_discount = shipping_fee if discount is not None and discount.kind == "free_shipping" else ZERO

    charged = [subtotals[i] - line_discounts[i] for i in range(len(lines))] + [shipping_fee - shipping_discount]
    rate = policy.vat_rate

    if policy.prices_include_vat:
        gross_total = sum(charged, ZERO)
        taxable = net_from_gross(gross_total, rate)
        nets = allocate(taxable, charged)
        vats = [amount - net for amount, net in zip(charged, nets, strict=True)]
        vat_total = gross_total - taxable
    else:
        nets = charged
        taxable = sum(nets, ZERO)
        vat_total = vat_for_net(taxable, rate)
        vats = allocate(vat_total, nets)

    priced_lines = tuple(
        PricedComponent(
            key=line.key,
            quantity=line.quantity,
            unit_price=to_money(line.unit_price),
            subtotal=subtotals[i],
            discount=line_discounts[i],
            net=nets[i],
            vat=vats[i],
            total=nets[i] + vats[i],
        )
        for i, line in enumerate(lines)
    )
    shipping = PricedComponent(
        key=SHIPPING_KEY,
        quantity=1,
        unit_price=shipping_fee,
        subtotal=shipping_fee,
        discount=shipping_discount,
        net=nets[-1],
        vat=vats[-1],
        total=nets[-1] + vats[-1],
    )
    return PricedCart(
        lines=priced_lines,
        shipping=shipping,
        prices_include_vat=policy.prices_include_vat,
        vat_rate=rate,
        subtotal=subtotal,
        eligible_subtotal=eligible_subtotal,
        item_discount=item_discount,
        shipping_discount=shipping_discount,
        taxable_amount=taxable,
        vat=vat_total,
        total=taxable + vat_total,
    )
