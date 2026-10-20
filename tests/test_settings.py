from django.conf import settings


def test_timezone_and_custom_user_are_configured():
    assert settings.TIME_ZONE == "Asia/Manila"
    assert settings.USE_TZ is True
    assert settings.AUTH_USER_MODEL == "accounts.User"
