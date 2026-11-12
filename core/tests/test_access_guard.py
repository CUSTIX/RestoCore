"""Every staff and API URL must refuse anonymous visitors. Walks the real URLconf, so a new view
that forgets its role check fails here without anyone remembering to add a test for it."""

import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver


def _walk(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def _concrete(route: str) -> str:
    """'app/sales/orders/<int:pk>/' -> '/app/sales/orders/1/' (dummy values for converters)."""
    route = re.sub(r"<int:\w+>", "1", route)
    route = re.sub(r"<(?:str|slug):\w+>", "x", route)
    route = re.sub(r"<[^>]+>", "1", route)
    return "/" + route.lstrip("^").rstrip("$")


ROUTES = sorted({_concrete(r) for r in _walk(get_resolver().url_patterns)})
STAFF = [r for r in ROUTES if r.startswith("/app/")]
API = [r for r in ROUTES if r.startswith("/api/")]


def test_url_walk_found_the_staff_area_and_api():
    assert len(STAFF) > 30 and API


@pytest.mark.django_db
@pytest.mark.parametrize("url", STAFF)
@pytest.mark.parametrize("method", ["get", "post"])
def test_staff_urls_send_anonymous_visitors_to_login(client, url, method):
    response = getattr(client, method)(url)
    assert response.status_code == 302, f"{method.upper()} {url} -> {response.status_code}"
    assert response["Location"].startswith("/accounts/login/")


@pytest.mark.django_db
@pytest.mark.parametrize("url", API)
def test_api_urls_refuse_requests_without_a_token(client, settings, url):
    settings.API_TOKEN = "configured-token"
    assert client.get(url).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("url", STAFF)
def test_staff_urls_refuse_a_signed_in_user_with_no_role(client, make_user, url):
    """Logged in but holding no role (e.g. a deactivated employee's leftover account)."""
    client.force_login(make_user(None))
    assert client.get(url).status_code in (403, 404)
