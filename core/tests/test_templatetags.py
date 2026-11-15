from decimal import Decimal

import pytest

from core.templatetags.core import money, percent


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("0.045"), "4.5%"),
        (Decimal("0.12"), "12%"),
        (Decimal("0.0250"), "2.5%"),
        (Decimal("1"), "100%"),
        (Decimal("0"), "0%"),
        (None, ""),
    ],
)
def test_percent_is_exact(value, expected):
    assert percent(value) == expected


def test_money_formats_two_places_with_separators():
    assert money(Decimal("1234.5")) == "1,234.50"
    assert money(None) == ""


def test_money_filter_rounds_half_up_like_the_order_math():
    """COR-08: Python's default is half-even (0.125 -> 0.12); every total in the app is half-up."""
    assert money(Decimal("0.125")) == "0.13"
    assert money(Decimal("50.025")) == "50.03"
    assert money(Decimal("2.675")) == "2.68"
