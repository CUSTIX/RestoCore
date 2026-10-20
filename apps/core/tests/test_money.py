from decimal import Decimal

import pytest

from apps.core.money import as_money


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", Decimal("10.00")),
        ("10.125", Decimal("10.13")),
        (10, Decimal("10.00")),
        (Decimal("9.994"), Decimal("9.99")),
    ],
)
def test_as_money_normalizes_to_centavos(value, expected):
    assert as_money(value) == expected


@pytest.mark.parametrize("value", [1.1, True])
def test_as_money_rejects_unsafe_numeric_types(value):
    with pytest.raises(TypeError):
        as_money(value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_as_money_rejects_non_finite_values(value):
    with pytest.raises(ValueError):
        as_money(value)
