import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice


@pytest.fixture
def owner_user():
    user = get_user_model().objects.create_user(
        email="owner-enforcement@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="owner"))
    return user


@pytest.mark.django_db
def test_mfa_policy_does_not_block_public_pages(client, owner_user):
    client.force_login(owner_user)

    response = client.get(reverse("website:home"))

    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(MFA_ENFORCEMENT_ENABLED=False)
def test_local_review_mode_allows_unenrolled_owner_to_use_internal_navigation(
    client,
    owner_user,
):
    client.force_login(owner_user)

    for url_name in (
        "core:workspace",
        "bookings:home",
        "orders:home",
        "inventory:home",
        "staff:home",
        "payroll:home",
        "pos:home",
        "reports:home",
    ):
        response = client.get(reverse(url_name))
        assert response.status_code == 200


@pytest.mark.django_db
def test_unenrolled_owner_is_sent_to_security_setup(client, owner_user):
    client.force_login(owner_user)

    response = client.get(reverse("core:workspace"))

    assert response.status_code == 302
    assert response.url == reverse("accounts:security")


@pytest.mark.django_db
def test_enrolled_owner_is_sent_to_mfa_challenge(client, owner_user):
    client.force_login(owner_user)
    TOTPDevice.objects.create(
        user=owner_user,
        name="Primary authenticator",
        confirmed=True,
    )

    response = client.get(reverse("core:workspace"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:mfa_challenge"))


@pytest.mark.django_db
def test_valid_totp_unlocks_internal_workspace(client, owner_user):
    client.force_login(owner_user)
    device = TOTPDevice.objects.create(
        user=owner_user,
        name="Primary authenticator",
        confirmed=True,
    )
    token = str(
        totp(
            device.bin_key,
            step=device.step,
            t0=device.t0,
            digits=device.digits,
            drift=device.drift,
        )
    ).zfill(device.digits)

    response = client.post(
        reverse("accounts:mfa_challenge"),
        {"token": token, "next": reverse("core:workspace")},
    )
    workspace = client.get(reverse("core:workspace"))

    assert response.status_code == 302
    assert response.url == reverse("core:workspace")
    assert workspace.status_code == 200


@pytest.mark.django_db
def test_recovery_code_unlocks_workspace_and_is_consumed(client, owner_user):
    client.force_login(owner_user)
    TOTPDevice.objects.create(
        user=owner_user,
        name="Primary authenticator",
        confirmed=True,
    )
    recovery_device = StaticDevice.objects.create(
        user=owner_user,
        name="Recovery codes",
        confirmed=True,
    )
    StaticToken.objects.create(device=recovery_device, token="recover-me")

    response = client.post(
        reverse("accounts:mfa_challenge"),
        {"token": "recover-me", "next": reverse("core:workspace")},
    )
    workspace = client.get(reverse("core:workspace"))

    assert response.status_code == 302
    assert workspace.status_code == 200
    assert not StaticToken.objects.filter(device=recovery_device, token="recover-me").exists()
