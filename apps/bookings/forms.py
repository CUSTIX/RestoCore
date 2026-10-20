from django import forms
from django.utils import timezone

from .models import Booking


class PublicBookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = (
            "guest_name",
            "guest_email",
            "guest_phone",
            "party_size",
            "starts_at",
            "notes",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_starts_at(self):
        starts_at = self.cleaned_data["starts_at"]
        if starts_at <= timezone.now():
            raise forms.ValidationError("Choose a reservation time in the future.")
        return starts_at

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("guest_email") and not cleaned_data.get("guest_phone"):
            raise forms.ValidationError("Provide an email address or phone number.")
        return cleaned_data
