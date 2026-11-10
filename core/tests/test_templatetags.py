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
