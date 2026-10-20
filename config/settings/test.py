"""Fast, isolated test settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = False
SECRET_KEY = "django-insecure-restocore-test-key"
ALLOWED_HOSTS = ["testserver", "localhost"]
DATABASES = {
    "default": env.db("TEST_DATABASE_URL", default="sqlite://:memory:"),
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
