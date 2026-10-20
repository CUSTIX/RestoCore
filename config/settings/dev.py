"""Development settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-restocore-local-development-only",
)
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]"],
)
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:8000", "http://127.0.0.1:8000"],
)
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgresql://restocore:restocore@127.0.0.1:5432/restocore",
    )
}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
MFA_ENFORCEMENT_ENABLED = env.bool("MFA_ENFORCEMENT_ENABLED", default=False)
