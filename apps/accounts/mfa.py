import secrets

from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

RECOVERY_CODE_COUNT = 10


def get_confirmed_totp_device(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).order_by("-created_at").first()


def get_or_create_pending_totp_device(user):
    device = TOTPDevice.objects.filter(user=user, confirmed=False).order_by("-created_at").first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="Primary authenticator", confirmed=False)
    return device


def rotate_recovery_codes(user) -> list[str]:
    StaticDevice.objects.filter(user=user, name="Recovery codes").delete()
    device = StaticDevice.objects.create(user=user, name="Recovery codes", confirmed=True)

    codes = [secrets.token_hex(4) for _ in range(RECOVERY_CODE_COUNT)]
    StaticToken.objects.bulk_create(StaticToken(device=device, token=code) for code in codes)
    return codes
