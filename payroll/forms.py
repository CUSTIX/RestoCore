from django import forms

from payroll.models import DeductionRate


class PeriodForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))


DeductionRateFormSet = forms.modelformset_factory(
    DeductionRate, fields=("name", "rate", "is_active"), extra=1, can_delete=False
)
