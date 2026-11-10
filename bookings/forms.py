import datetime as dt

from django import forms
from django.utils import timezone

from bookings.models import Booking
from bookings.services import MAX_PARTY_SIZE, time_slots


def _slot_choices():
    return [(t.strftime("%H:%M"), t.strftime("%I:%M %p").lstrip("0")) for t in time_slots()]


class BookingForm(forms.ModelForm):
    time = forms.TypedChoiceField(
        choices=_slot_choices, coerce=lambda v: dt.datetime.strptime(v, "%H:%M").time()
    )
    party_size = forms.IntegerField(min_value=1, max_value=MAX_PARTY_SIZE)

    class Meta:
        model = Booking
        fields = ("name", "phone", "email", "party_size", "date", "time", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
        }
        help_texts = {"notes": "Allergies, high chair, celebrations… (optional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
        if self.instance.pk and self.instance.time:
            self.initial["time"] = self.instance.time.strftime("%H:%M")


class PublicBookingForm(BookingForm):
    # Honeypot: real people never see or fill this field; bots often do.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
        label="Leave this empty",
    )

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam check failed.")
        return ""


class BookingFilterForm(forms.Form):
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses"), *Booking.Status.choices]
    )
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={"type": "search", "placeholder": "Name, phone, email or reference"}
        ),
    )
