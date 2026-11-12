import re
from pathlib import Path

import pytest
from django.conf import settings


def _csp_directives(response) -> dict[str, str]:
    policy = response["Content-Security-Policy"]
    return {d.split()[0]: d for d in (part.strip() for part in policy.split(";")) if d}


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/", "/menu/", "/book/", "/accounts/login/"])
def test_public_pages_send_security_headers(client, url):
    response = client.get(url)
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "camera=()" in response["Permissions-Policy"]
    csp = _csp_directives(response)
    assert csp["script-src"] == "script-src 'self'"  # no inline JS, no eval, no third parties
    assert csp["object-src"] == "object-src 'none'"
    assert csp["frame-ancestors"] == "frame-ancestors 'none'"
    assert "'unsafe-inline'" not in csp["style-src-elem"]


@pytest.mark.django_db
def test_signed_in_pages_are_never_cached(client_for):
    response = client_for("Manager").get("/app/")
    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_public_pages_stay_cacheable_for_visitors(client):
    assert "no-store" not in client.get("/").get("Cache-Control", "")


def test_session_and_csrf_cookies_are_not_readable_by_javascript():
    assert settings.SESSION_COOKIE_HTTPONLY and settings.CSRF_COOKIE_HTTPONLY
    assert settings.SESSION_COOKIE_AGE <= 12 * 60 * 60


TEMPLATE_DIRS = [p for p in Path(settings.BASE_DIR).glob("*/templates") if p.parent.name != "local"]
TEMPLATES = sorted(f for d in TEMPLATE_DIRS for f in d.rglob("*.html"))
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)(?![^>]*application/(ld\+)?json)[^>]*>", re.I)
INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=\s*['\"]", re.I)


def test_templates_were_found():
    assert len(TEMPLATES) > 40


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: str(p.relative_to(settings.BASE_DIR)))
def test_templates_have_no_inline_javascript(template):
    """The CSP forbids inline JS; this catches it at test time instead of as a broken page."""
    html = template.read_text(encoding="utf-8")
    assert not INLINE_SCRIPT.search(html), "inline <script>: move it to a static .js file"
    assert not INLINE_HANDLER.search(html), "inline on*= handler: use a data-* attribute + JS"


@pytest.mark.django_db
def test_server_errors_show_a_friendly_page_without_details(settings):
    """DEBUG off: a crash returns our 500 page, never a traceback or settings."""
    from unittest import mock

    from django.test import Client

    settings.DEBUG = False
    client = Client(raise_request_exception=False)
    with mock.patch("website.views.HomeView.get_context_data", side_effect=RuntimeError("boom")):
        response = client.get("/")
    html = response.content.decode()
    assert response.status_code == 500
    assert "We spilled something" in html
    assert "boom" not in html and "Traceback" not in html and "SECRET_KEY" not in html
