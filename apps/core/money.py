from decimal import ROUND_HALF_UP, Decimal

MONEY_DECIMAL_PLACES = 2
MONEY_MAX_DIGITS = 12
MONEY_QUANTUM = Decimal("0.01")


def as_money(value: Decimal | int | str) -> Decimal:
    """Normalize money to two decimal places and reject binary floating-point input."""

    if isinstance(value, (bool, float)):
        raise TypeError("Money values must use Decimal, int, or str; floats are not allowed.")

    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError("Money values must be finite.")

    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
