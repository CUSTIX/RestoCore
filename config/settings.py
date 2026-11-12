"""RestoCore settings. Every environment-specific value comes from environment variables."""

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Required: fail loudly at startup instead of running with a guessable key.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


# Safe default: DEBUG is off unless explicitly turned on.
DEBUG = env_bool("DJANGO_DEBUG")

_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()]
_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
# Render sets this to the service's public hostname (e.g. restocore.onrender.com).
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

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
# Public demo deployments: show the demo accounts on the login page even with DEBUG off.
# Pair with DEMO_RESET_ON_START=true (bin/start.sh) so visitors always get fresh demo data.
DEMO_MODE = env_bool("DEMO_MODE")
# The demo logins listed on the login page. With DEMO_MODE on they can't be edited, demoted or
# deactivated through staff management, so one visitor can't lock the next one out.
DEMO_ACCOUNTS = ("owner", "manager", "cashier", "kitchen", "staff")
# Header (as a request.META key) holding the real visitor IP, set by a proxy that overwrites it,
# e.g. HTTP_CF_CONNECTING_IP behind Cloudflare/Render. Empty: use the socket address.
# Used for sign-in throttling; never point this at X-Forwarded-For, which callers can forge.
CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "")

# Sales tax added on top of menu prices, as a fraction (0.12 = 12%). Configurable per country.
SALES_TAX_RATE = os.environ.get("SALES_TAX_RATE", "0.12")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files efficiently from the app itself (no separate web server).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # CSP, Permissions-Policy, no caching of signed-in pages. After auth: it reads request.user.
    "core.middleware.SecurityHeadersMiddleware",
]

# Content Security Policy. No inline JavaScript anywhere (templates use data-* attributes that the
# static scripts pick up), so script-src is 'self' only. Inline style *attributes* are allowed
# (dynamic widths, animation delays) but <style> elements are not. Google Fonts is the only
# third party.
_FONT_CSS = "https://fonts.googleapis.com"
_FONT_FILES = "https://fonts.gstatic.com"
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        f"style-src 'self' 'unsafe-inline' {_FONT_CSS}",  # fallback for pre-CSP3 browsers
        f"style-src-elem 'self' {_FONT_CSS}",
        "style-src-attr 'unsafe-inline'",
        f"font-src 'self' {_FONT_FILES}",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
# Sessions: at most one long shift, then sign in again. Our JS never reads the CSRF cookie.
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), "
    "gyroscope=(), accelerometer=(), browsing-topics=()"
)

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


def database_from_url(url: str) -> dict:
    """Turn a postgres:// URL (what hosted Postgres such as Neon hands out) into Django settings.

    Query parameters (e.g. sslmode=require) are passed to the driver as connection options.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must start with postgres:// or postgresql://")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        "OPTIONS": dict(parse_qsl(parts.query)),
    }


# Local/Compose: separate POSTGRES_* variables. Hosted: one DATABASE_URL takes precedence.
DATABASES = {
    "default": database_from_url(os.environ["DATABASE_URL"])
    if os.environ.get("DATABASE_URL")
    else {
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
# Production: compressed, fingerprinted files (needs collectstatic, done in the prod image build).
# Dev and tests: plain storage so no collectstatic step is needed.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if env_bool("DJANGO_STATIC_MANIFEST")
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# Outside production there is no collectstatic step: let WhiteNoise serve straight from app folders.
WHITENOISE_USE_FINDERS = not env_bool("DJANGO_STATIC_MANIFEST")

# HTTPS hardening. Turn on with DJANGO_HTTPS=true when the site is served over HTTPS
# (behind a proxy that sets X-Forwarded-Proto). `manage.py check --deploy` passes with it on.
if env_bool("DJANGO_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)
    if not SECURE_HSTS_PRELOAD:
        # Preload-list submission is hard to undo, so it is opt-in (DJANGO_HSTS_PRELOAD=true).
        SILENCED_SYSTEM_CHECKS = ["security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
