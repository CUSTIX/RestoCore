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
# A javascript: URL is inline script too: the CSP blocks it, so the link silently does nothing.
JAVASCRIPT_URL = re.compile(r"""(?:href|src|action|formaction)\s*=\s*["']\s*javascript:""", re.I)


def test_templates_were_found():
    assert len(TEMPLATES) > 40


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: str(p.relative_to(settings.BASE_DIR)))
def test_templates_have_no_inline_javascript(template):
    """The CSP forbids inline JS; this catches it at test time instead of as a broken page."""
    html = template.read_text(encoding="utf-8")
    assert not INLINE_SCRIPT.search(html), "inline <script>: move it to a static .js file"
    assert not INLINE_HANDLER.search(html), "inline on*= handler: use a data-* attribute + JS"
    assert not JAVASCRIPT_URL.search(html), "javascript: URL is blocked by the CSP: use a real link"


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


@pytest.mark.django_db
def test_stale_form_token_shows_a_friendly_page_and_saves_nothing(make_user):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    response = client.post("/accounts/login/", {"username": "x", "password": "y"})
    html = response.content.decode()
    assert response.status_code == 403
    assert "open a little too long" in html and "CSRF" not in html


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: str(p.relative_to(settings.BASE_DIR)))
def test_no_preconnect_hints_the_csp_would_refuse(template):
    """UX-16: a preconnect to Google Fonts is governed by connect-src, which only allows 'self',
    so every page logged a console error. The stylesheet itself is allowed and still loads."""
    assert 'rel="preconnect"' not in template.read_text(encoding="utf-8")


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/", "/menu/"])
def test_public_pages_start_with_a_skip_link(client, url):
    html = client.get(url).content.decode()
    assert html.index('class="skip-link"') < html.index("<header")
    assert 'id="main"' in html


@pytest.mark.django_db
def test_staff_pages_start_with_a_skip_link(client_for):
    html = client_for("Manager").get("/app/").content.decode()
    assert html.index('class="skip-link" href="#main"') < html.index("<aside")
    assert 'id="main"' in html


def _css(name):
    return (Path(settings.BASE_DIR) / "core" / "static" / "core" / name).read_text("utf-8")


def test_pos_checkout_bar_covers_tablets_not_only_phones():
    """Between 641 and 1100 px the POS is one column, so the total bar must show there too."""
    css = _css("app.css")
    rule = css.index("  .pos-mobile-bar { display: flex;")
    opening = css.rindex("@media", 0, rule)
    assert css[opening : css.index("{", opening)].strip() == "@media (max-width: 1100px)"


def test_auto_reload_waits_while_someone_is_typing():
    js = _css("motion.js")
    assert "document.activeElement" in js and "defaultValue" in js


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,url,code", [("Manager", "/nope/", 404), ("Kitchen", "/app/sales/pos/", 403)]
)
def test_error_pages_have_a_main_landmark(client_for, role, url, code):
    """403 and 404 pages are whole pages, so screen readers need a <main> to jump to (UX-21)."""
    response = client_for(role).get(url)
    assert response.status_code == code
    assert '<main class="error-page" id="main">' in response.content.decode()


def test_error_and_warning_toasts_do_not_vanish_on_their_own():
    js = _css("motion.js")
    assert (
        'classList.contains("toast--error")' in js and 'classList.contains("toast--warning")' in js
    )
    assert '"focusin"' in js


def test_touch_targets_reach_44px_on_coarse_pointers():
    assert "@media (pointer: coarse)" in _css("app.css")
    css = _css("app.css")
    coarse = css[css.index("@media (pointer: coarse)") :]
    assert ".stepper button { width: 44px; height: 44px; }" in coarse
    assert ".icon-btn { width: 44px; height: 44px; }" in coarse
