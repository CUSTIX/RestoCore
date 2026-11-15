"""One rounding rule for every amount of money: cents, halves rounded up.

Python's default (`round`, `Decimal.quantize`, `format`) is half-even, which disagrees with the
half-up totals a cashier and a payslip expect. Use this everywhere money is computed or shown.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
