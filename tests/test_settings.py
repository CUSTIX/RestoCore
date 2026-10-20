from django.conf import settings


def test_timezone_and_custom_user_are_configured():
    assert settings.TIME_ZONE == "Asia/Manila"
    assert settings.USE_TZ is True
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_authentication_security_stack_is_configured():
    assert settings.AUTHENTICATION_BACKENDS[0] == "axes.backends.AxesStandaloneBackend"
    assert "django_otp.middleware.OTPMiddleware" in settings.MIDDLEWARE
    assert settings.MIDDLEWARE[-1] == "axes.middleware.AxesMiddleware"
    assert settings.AXES_FAILURE_LIMIT == 5
