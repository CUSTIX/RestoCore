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


class TestAccessibleFields:
    """A rejected form must tell a screen reader which field failed and why (UX-04)."""

    @staticmethod
    def _render(data):
        from django import forms
        from django.template.loader import render_to_string

        class Demo(forms.Form):
            name = forms.CharField(help_text="As on your card.")

        return render_to_string("core/partials/form.html", {"form": Demo(data)})

    def test_rejected_field_is_invalid_and_points_at_its_error(self):
        html = self._render({"name": ""})
        assert 'aria-invalid="true"' in html
        assert 'aria-describedby="id_name_helptext id_name_error"' in html
        assert 'id="id_name_error"' in html
        assert 'id="id_name_helptext"' in html

    def test_valid_field_is_not_marked_invalid(self):
        html = self._render({"name": "Ana"})
        assert "aria-invalid" not in html
        assert 'aria-describedby="id_name_helptext"' in html
        assert "_error" not in html

    def test_unbound_form_has_no_error_markup(self):
        html = self._render(None)
        assert "aria-invalid" not in html

    def test_form_level_error_is_announced(self):
        from django import forms
        from django.template.loader import render_to_string

        class Demo(forms.Form):
            def clean(self):
                raise forms.ValidationError("Wrong username or password.")

        html = render_to_string("core/partials/form.html", {"form": Demo({})})
        assert 'role="alert"' in html
        assert "Wrong username or password." in html
