"""RestoCore settings. Every environment-specific value comes from environment variables."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Required: fail loudly at startup instead of running with a guessable key.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Safe default: DEBUG is off unless explicitly turned on.
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # RestoCore modules (one app per module; see CLAUDE.md)
    "core",
    "accounts",
    "dashboard",
    "website",
    "bookings",
    "inventory",
    "sales",
    "staff",
    "payroll",
    "api",
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "website:home"

RESTAURANT_NAME = os.environ.get("RESTAURANT_NAME", "Little Roast Café")
CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "₱")

# Read-only API for the MCP server. Empty token = API disabled.
API_TOKEN = os.environ.get("RESTOCORE_API_TOKEN", "")

# Sales tax added on top of menu prices, as a fraction (0.12 = 12%). Configurable per country.
SALES_TAX_RATE = os.environ.get("SALES_TAX_RATE", "0.12")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # local/templates (gitignored) comes first so a developer can override branding locally.
        "DIRS": [BASE_DIR / "local" / "templates", BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.restocore",
                "website.context_processors.cafe_status",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "restocore"),
        "USER": os.environ.get("POSTGRES_USER", "restocore"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# Times are stored in UTC (USE_TZ); TIME_ZONE is the restaurant's local time for display and forms.
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
