from django import forms


class TOTPVerificationForm(forms.Form):
    token = forms.CharField(
        label="Authenticator code",
        max_length=6,
        min_length=6,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
            }
        ),
    )

    def clean_token(self):
        token = self.cleaned_data["token"]
        if not token.isdigit():
            raise forms.ValidationError("Enter the 6-digit code from your authenticator app.")
        return token


class MFAChallengeForm(forms.Form):
    token = forms.CharField(
        label="Verification code",
        max_length=64,
        strip=True,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )
