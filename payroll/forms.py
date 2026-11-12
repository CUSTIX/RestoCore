from decimal import Decimal

from django import forms

from payroll.models import DeductionRate


class PeriodForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "data-not-before": "start_date",
                "data-rule-message": "The period can't end before it starts.",
            }
        )
    )


RATE_HINT = "Enter the rate as a fraction below 1: 0.08 means 8%."


class DeductionRateForm(forms.ModelForm):
    # Typing "8" for 8% is the classic mistake (an 800% deduction): catch it with a clear
    # message in the browser and on the server, not a database constraint name.
    rate = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("0.9999"),
        decimal_places=4,
        max_digits=5,
        # Django %-formats these messages (with the limit value), so the % must be escaped.
        error_messages={
            "max_value": RATE_HINT.replace("%", "%%"),
            "min_value": "The rate can't be negative.",
        },
        widget=forms.NumberInput(attrs={"data-max-message": RATE_HINT, "step": "0.0001"}),
        help_text="0.08 = 8%",
    )

    class Meta:
        model = DeductionRate
        fields = ("name", "rate", "is_active")


DeductionRateFormSet = forms.modelformset_factory(
    DeductionRate, form=DeductionRateForm, extra=1, can_delete=False
)
