from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from core.roles import ALL_ROLES
from staff.models import LeaveRequest, Shift
from staff.selectors import active_employees

ROLE_CHOICES = [(r, r) for r in ALL_ROLES]


class EmployeeForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    position = forms.CharField(max_length=80)
    phone = forms.CharField(max_length=32, required=False)
    hourly_rate = forms.DecimalField(min_value=Decimal("0"), max_digits=8, decimal_places=2)
    hire_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    is_active = forms.BooleanField(required=False, initial=True, label="Active (can log in)")


class NewEmployeeForm(EmployeeForm):
    username = forms.RegexField(
        regex=r"^[\w.@+-]+$", max_length=150, help_text="Letters, digits and @/./+/-/_ only."
    )
    password = forms.CharField(widget=forms.PasswordInput, help_text="At least 8 characters.")

    field_order = ["username", "password"]

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class ShiftForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=active_employees())
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    end_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={
                "type": "time",
                "data-after": "start_time",
                "data-rule-message": "The shift must end after it starts.",
            }
        )
    )
    note = forms.CharField(max_length=120, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = active_employees()

    @classmethod
    def from_shift(cls, shift: Shift):
        return cls(
            initial={
                "employee": shift.employee,
                "date": shift.date,
                "start_time": shift.start_time,
                "end_time": shift.end_time,
                "note": shift.note,
            }
        )


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ("leave_type", "start_date", "end_date", "reason")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "data-not-before": "start_date",
                    "data-rule-message": "The leave can't end before it starts.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate().isoformat()
        self.fields["start_date"].widget.attrs["min"] = today
        self.fields["end_date"].widget.attrs["min"] = today


class LeaveReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])
    note = forms.CharField(max_length=300, required=False)


class WeekForm(forms.Form):
    start = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Week starting"
    )


class AttendanceFilterForm(forms.Form):
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


class LeaveFilterForm(forms.Form):
    status = forms.ChoiceField(required=False, choices=[("", "All"), *LeaveRequest.Status.choices])
