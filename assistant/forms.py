from django import forms

from assistant.services import MAX_QUESTION


class AskForm(forms.Form):
    question = forms.CharField(
        max_length=MAX_QUESTION,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Ask about sales, bookings, stock, staff or payroll…",
                "maxlength": MAX_QUESTION,
                "autocomplete": "off",
            }
        ),
        error_messages={"required": "Type a question first."},
    )
