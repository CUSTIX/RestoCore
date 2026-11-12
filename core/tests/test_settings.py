import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured

import config.settings as settings_module
from config.settings import database_from_url


def test_database_url_is_parsed_like_hosted_postgres_hands_it_out():
    db = database_from_url(
        "postgresql://app_user:p%40ss%2Fword@ep-cool-1.ap-southeast-1.aws.neon.tech/restocore"
        "?sslmode=require&channel_binding=require"
    )
    assert db["ENGINE"] == "django.db.backends.postgresql"
    assert db["NAME"] == "restocore"
    assert db["USER"] == "app_user"
    assert db["PASSWORD"] == "p@ss/word"  # URL-encoded characters are decoded
    assert db["HOST"] == "ep-cool-1.ap-southeast-1.aws.neon.tech"
    assert db["PORT"] == ""  # driver default (5432)
    assert db["OPTIONS"] == {"sslmode": "require", "channel_binding": "require"}


def test_database_url_keeps_an_explicit_port():
    assert database_from_url("postgres://u:p@db:6543/x")["PORT"] == "6543"


def test_database_url_with_wrong_scheme_is_rejected():
    with pytest.raises(ImproperlyConfigured):
        database_from_url("mysql://u:p@db/x")


@pytest.fixture
def reload_settings(monkeypatch):
    """Re-run the settings module under a patched environment, then restore it."""

    def _reload(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(settings_module)

    yield _reload
    monkeypatch.undo()
    importlib.reload(settings_module)


def test_render_hostname_is_allowed_and_trusted_for_csrf(reload_settings):
    s = reload_settings(RENDER_EXTERNAL_HOSTNAME="restocore.onrender.com")
    assert "restocore.onrender.com" in s.ALLOWED_HOSTS
    assert "https://restocore.onrender.com" in s.CSRF_TRUSTED_ORIGINS


def test_database_url_takes_precedence_over_postgres_vars(reload_settings):
    s = reload_settings(DATABASE_URL="postgres://u:p@hosted:5432/live", POSTGRES_HOST="db")
    assert s.DATABASES["default"]["HOST"] == "hosted"
    assert s.DATABASES["default"]["NAME"] == "live"
