from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_audit_event

from .forms import TOTPVerificationForm
from .mfa import (
    get_confirmed_totp_device,
    get_or_create_pending_totp_device,
    rotate_recovery_codes,
)
from .security import requires_mfa


@login_required
def security_settings(request):
    confirmed_device = get_confirmed_totp_device(request.user)
    return render(
        request,
        "accounts/security.html",
        {
            "confirmed_device": confirmed_device,
            "mfa_required": requires_mfa(request.user),
        },
    )


@login_required
@require_POST
def begin_mfa_setup(request):
    if get_confirmed_totp_device(request.user) is not None:
        messages.info(request, "Multi-factor authentication is already configured.")
        return redirect("accounts:security")

    get_or_create_pending_totp_device(request.user)
    return redirect("accounts:mfa_setup")


@login_required
@require_http_methods(["GET", "POST"])
def mfa_setup(request):
    if get_confirmed_totp_device(request.user) is not None:
        return redirect("accounts:security")

    device = get_or_create_pending_totp_device(request.user)
    form = TOTPVerificationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if device.verify_token(form.cleaned_data["token"]):
            device.confirmed = True
            device.save(update_fields=["confirmed"])

            codes = rotate_recovery_codes(request.user)
            record_audit_event(
                action="accounts.mfa_enabled",
                actor=request.user,
                target=request.user,
                after={"mfa_enabled": True},
            )
            request.session["new_recovery_codes"] = codes
            messages.success(request, "Multi-factor authentication is now configured.")
            return redirect("accounts:recovery_codes")

        form.add_error("token", "That code could not be verified. Try a new code.")

    return render(
        request,
        "accounts/mfa_setup.html",
        {
            "device": device,
            "form": form,
        },
    )


@login_required
def recovery_codes(request):
    codes = request.session.pop("new_recovery_codes", None)
    if not codes:
        return redirect("accounts:security")
    return render(request, "accounts/recovery_codes.html", {"codes": codes})


@login_required
@require_POST
def rotate_codes(request):
    if get_confirmed_totp_device(request.user) is None:
        messages.error(request, "Configure multi-factor authentication first.")
        return redirect("accounts:security")

    request.session["new_recovery_codes"] = rotate_recovery_codes(request.user)
    record_audit_event(
        action="accounts.recovery_codes_rotated",
        actor=request.user,
        target=request.user,
    )
    messages.success(request, "Your previous recovery codes are no longer valid.")
    return redirect("accounts:recovery_codes")
