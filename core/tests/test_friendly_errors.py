"""Rule violations must read like advice, never like a database constraint name."""

import pytest


def _all_errors(form_or_set) -> str:
    form_or_set.is_valid()
    text = str(form_or_set.errors)
    if hasattr(form_or_set, "non_form_errors"):
        text += str(form_or_set.non_form_errors())
    return text


@pytest.mark.django_db
def test_zero_price_says_so(stocked_menu):
    from sales.forms import MenuItemForm

    errors = _all_errors(
        MenuItemForm({"category": stocked_menu["category"].pk, "name": "X", "price": "0"})
    )
    assert "more than zero" in errors and "Constraint" not in errors


@pytest.mark.django_db
def test_rate_typed_as_percent_explains_the_fraction():
    from payroll.forms import DeductionRateFormSet

    errors = _all_errors(
        DeductionRateFormSet(
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-0-name": "Tax",
                "form-0-rate": "8",
                "form-0-is_active": "on",
            }
        )
    )
    assert "0.08 means 8%" in errors and "Constraint" not in errors


@pytest.mark.django_db
def test_negative_cost_and_reorder_level_are_refused():
    from inventory.forms import NewItemForm

    form = NewItemForm(
        {
            "name": "Sugar syrup",
            "unit": "l",
            "quantity": "1",
            "reorder_level": "-1",
            "cost_per_unit": "-5",
            "is_active": "on",
        }
    )
    assert not form.is_valid()
    assert {"reorder_level", "cost_per_unit"} <= set(form.errors)


def test_every_check_constraint_has_a_human_message():
    from django.apps import apps
    from django.db.models import CheckConstraint

    missing = [
        f"{model._meta.label}.{c.name}"
        for model in apps.get_models()
        for c in model._meta.constraints
        if isinstance(c, CheckConstraint) and c.violation_error_message is None
    ]
    assert missing == []
