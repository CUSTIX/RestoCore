"""Every link a role can see must work for that role.

Seeds the demo data, signs in as each demo role, and follows every staff link reachable from
the dashboard. A link that answers 403/404/500 is either a page shown to someone who can't use
it, or a crash: e.g. the week view's "Add shift" links once returned 500, which no
page-by-page test noticed because none opened the form with ?date=.
"""

import html
import re
from collections import deque
from urllib.parse import urlsplit

import pytest
from django.core.management import call_command

ROLES = ("owner", "manager", "cashier", "kitchen", "staff")
HREF = re.compile(r'href="([^"#]+)"')
MAX_PAGES = 150


def _links(page_html: str, here: str) -> set[str]:
    found = set()
    for raw in HREF.findall(page_html):
        href = html.unescape(raw)
        parts = urlsplit(href)
        if parts.netloc or not (parts.path.startswith("/app/") or href == "/accounts/password/"):
            continue
        query = "&".join(q for q in parts.query.split("&") if q and not q.startswith("page="))
        found.add(parts.path + (f"?{query}" if query else ""))
    return found


@pytest.fixture
def demo(db, settings):
    settings.DEMO_MODE = False
    call_command("seed_demo", verbosity=0)


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
def test_every_link_a_role_sees_works_for_that_role(client, demo, role):
    assert client.login(username=role, password="restocore-demo")
    seen, queue, broken = set(), deque(["/app/"]), []
    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        response = client.get(url)
        if response.status_code >= 400:
            broken.append((url, response.status_code))
            continue
        if response.status_code != 200 or "text/html" not in response.get("Content-Type", ""):
            continue
        queue.extend(_links(response.content.decode(), url) - seen)
    assert broken == [], f"{role} sees links that fail: {broken}"
    assert len(seen) > 3  # it really crawled something
