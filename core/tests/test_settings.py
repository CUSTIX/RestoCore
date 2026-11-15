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
    assert db["OPTIONS"] == {
        "connect_timeout": 10,
        "sslmode": "require",
        "channel_binding": "require",
    }


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


def test_every_app_with_tests_is_collected():
    """pytest only looks in `testpaths`: an app missing there has its tests silently skipped
    (in CI too). Ask RestoCore's tests were missed exactly like this once."""
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    testpaths = set(config["tool"]["pytest"]["ini_options"]["testpaths"])
    apps_with_tests = {p.parent.name for p in root.glob("*/tests") if p.is_dir()}
    assert apps_with_tests <= testpaths, apps_with_tests - testpaths


def test_hosted_database_reuses_connections_and_times_out_instead_of_hanging():
    """OPS-03: a fresh TLS connection per request is slow against Neon, and a suspended database
    must fail fast instead of holding a worker until gunicorn's timeout."""
    config = database_from_url("postgresql://u:p@host.example/db?sslmode=require")
    assert config["CONN_MAX_AGE"] == 60 and config["CONN_HEALTH_CHECKS"] is True
    assert config["OPTIONS"]["connect_timeout"] == 10 and config["OPTIONS"]["sslmode"] == "require"


def test_an_explicit_connect_timeout_in_the_url_wins():
    config = database_from_url("postgresql://u:p@host.example/db?connect_timeout=3")
    assert config["OPTIONS"]["connect_timeout"] == "3"


def test_log_lines_carry_time_level_and_logger_name():
    """OPS-09: bare messages cannot be placed in time or traced to a module."""
    handler = settings_module.LOGGING["handlers"]["console"]
    fmt = settings_module.LOGGING["formatters"][handler["formatter"]]["format"]
    assert "%(asctime)s" in fmt and "%(levelname)s" in fmt and "%(name)s" in fmt


def test_every_environment_variable_the_settings_read_is_documented():
    """OPS-12: a variable that is read but not in .env.example cannot be discovered or set by
    anyone who did not write the code (nine had drifted out of it)."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = (root / "config" / "settings.py").read_text()
    example = (root / ".env.example").read_text()
    read = set(re.findall(r'(?:environ\.get|env_bool|environ\[)\(?\s*"([A-Z][A-Z0-9_]+)"', source))
    provided_by_the_host = {"RENDER_EXTERNAL_HOSTNAME"}
    missing = {name for name in read - provided_by_the_host if name not in example}
    assert not missing, f"Add these to .env.example: {sorted(missing)}"
