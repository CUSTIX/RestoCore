import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.audit.models import AuditEvent


@pytest.fixture
def owner_user():
    user = get_user_model().objects.create_user(
        email="owner-mfa@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="owner"))
    return user


@pytest.mark.django_db
def test_security_page_requires_login(client):
    response = client.get(reverse("accounts:security"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_owner_security_page_marks_mfa_required(client, owner_user):
    client.force_login(owner_user)

    response = client.get(reverse("accounts:security"))

    assert response.status_code == 200
    assert b"Required" in response.content
    assert b"Set up authenticator" in response.content


@pytest.mark.django_db
def test_begin_mfa_setup_creates_pending_device(client, owner_user):
    client.force_login(owner_user)

    response = client.post(reverse("accounts:mfa_begin"))

    assert response.status_code == 302
    assert response.url == reverse("accounts:mfa_setup")
    device = TOTPDevice.objects.get(user=owner_user)
    assert device.confirmed is False


@pytest.mark.django_db
def test_valid_totp_enables_device_and_creates_recovery_codes(client, owner_user):
    client.force_login(owner_user)
    client.post(reverse("accounts:mfa_begin"))
    device = TOTPDevice.objects.get(user=owner_user, confirmed=False)
    token = str(
        totp(
            device.bin_key,
            step=device.step,
            t0=device.t0,
            digits=device.digits,
            drift=device.drift,
        )
    ).zfill(device.digits)

    response = client.post(reverse("accounts:mfa_setup"), {"token": token})

    assert response.status_code == 302
    assert response.url == reverse("accounts:recovery_codes")
    device.refresh_from_db()
    assert device.confirmed is True
    recovery_device = StaticDevice.objects.get(user=owner_user, name="Recovery codes")
    assert StaticToken.objects.filter(device=recovery_device).count() == 10
    assert AuditEvent.objects.filter(
        actor=owner_user,
        action="accounts.mfa_enabled",
    ).exists()


@pytest.mark.django_db
def test_recovery_codes_are_only_rendered_from_fresh_session(client, owner_user):
    client.force_login(owner_user)
    session = client.session
    session["new_recovery_codes"] = ["alpha123", "beta456"]
    session.save()

    response = client.get(reverse("accounts:recovery_codes"))
    second_response = client.get(reverse("accounts:recovery_codes"))

    assert response.status_code == 200
    assert b"alpha123" in response.content
    assert second_response.status_code == 302
    assert second_response.url == reverse("accounts:security")


@pytest.mark.django_db
def test_rotating_recovery_codes_invalidates_previous_codes(client, owner_user):
    client.force_login(owner_user)
    TOTPDevice.objects.create(user=owner_user, name="Primary authenticator", confirmed=True)
    old_device = StaticDevice.objects.create(
        user=owner_user,
        name="Recovery codes",
        confirmed=True,
    )
    StaticToken.objects.create(device=old_device, token="old-code")

    response = client.post(reverse("accounts:rotate_codes"))

    assert response.status_code == 302
    assert response.url == reverse("accounts:recovery_codes")
    assert not StaticToken.objects.filter(token="old-code").exists()
    new_device = StaticDevice.objects.get(user=owner_user, name="Recovery codes")
    assert StaticToken.objects.filter(device=new_device).count() == 10
    assert AuditEvent.objects.filter(
        actor=owner_user,
        action="accounts.recovery_codes_rotated",
    ).exists()
