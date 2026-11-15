from decimal import Decimal

import pytest

from core.money import money

D = Decimal


@pytest.mark.parametrize(
    "value,expected",
    [
        (D("0.125"), D("0.13")),  # half-even would give 0.12
        (D("0.135"), D("0.14")),
        (D("100.05") / 2, D("50.03")),
        (D("-0.125"), D("-0.13")),  # away from zero, like cash rounding
        (D("10"), D("10.00")),
    ],
)
def test_money_rounds_half_up_to_cents(value, expected):
    assert money(value) == expected
    assert money(value).as_tuple().exponent == -2
