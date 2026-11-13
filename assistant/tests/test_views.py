"""Ask RestoCore page: Owner only, works with and without JavaScript, escapes model output."""

import pytest

from assistant import services
from assistant.tests.test_services import FakeModel, call, text

pytestmark = pytest.mark.django_db
URL = "/app/assistant/"


@pytest.fixture(autouse=True)
def key(settings):
    settings.ASSISTANT_API_KEY = "test-key"


@pytest.fixture
def fake(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(services, "GeminiClient", lambda: model)
    return model


@pytest.mark.parametrize(
    "role,status",
    [("Owner", 200), ("Manager", 403), ("Cashier", 403), ("Kitchen", 403), ("Staff", 403)],
)
def test_only_the_owner_can_open_or_ask(client_for, fake, role, status):
    fake.turns = [text("ok")]
    client = client_for(role)
    assert client.get(URL).status_code == status
    assert client.post(URL, {"question": "sales?"}).status_code == (302 if status == 200 else 403)


def test_anonymous_users_go_to_login(client):
    response = client.get(URL)
    assert response.status_code == 302 and "/accounts/login/" in response["Location"]


def test_nav_link_only_for_the_owner(client_for):
    assert URL in client_for("Owner").get("/app/").content.decode()
    assert URL not in client_for("Manager").get("/app/").content.decode()


def test_ask_with_javascript_returns_blocks_and_sources(client_for, fake, stocked_menu):
    fake.turns = [call("get_menu"), text("**1** dish:\n- Rice bowl")]
    response = client_for("Owner").post(
        URL, {"question": "menu?"}, headers={"X-Requested-With": "fetch"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == ["Menu"]
    assert body["blocks"][1] == {"type": "ul", "items": [[{"text": "Rice bowl"}]]}


def test_ask_without_javascript_redirects_and_shows_the_conversation(client_for, fake):
    fake.turns = [text("All good today.")]
    client = client_for("Owner")
    assert client.post(URL, {"question": "How are we doing?"}).status_code == 302
    html = client.get(URL).content.decode()
    assert "How are we doing?" in html and "All good today." in html


def test_model_output_is_escaped(client_for, fake):
    fake.turns = [text("<script>alert(1)</script> **<img src=x onerror=alert(2)>**")]
    client = client_for("Owner")
    client.post(URL, {"question": "<b>hi</b>"})
    html = client.get(URL).content.decode()
    assert "<script>alert(1)" not in html and "<img src=x" not in html and "<b>hi</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_errors_are_friendly(client_for, fake, settings):
    client = client_for("Owner")
    empty = client.post(URL, {"question": ""}, headers={"X-Requested-With": "fetch"})
    assert empty.status_code == 400 and "Type a question" in empty.json()["error"]
    settings.ASSISTANT_HOURLY_LIMIT = 0
    limited = client.post(URL, {"question": "hi"}, headers={"X-Requested-With": "fetch"})
    assert limited.status_code == 503 and "this hour" in limited.json()["error"]
    assert "this hour" in client.get(URL).content.decode()  # and the page says so up front


def test_too_long_questions_are_refused(client_for, fake):
    response = client_for("Owner").post(
        URL, {"question": "x" * 501}, headers={"X-Requested-With": "fetch"}
    )
    assert response.status_code == 400


def test_new_conversation_clears_history(client_for, fake):
    fake.turns = [text("first answer")]
    client = client_for("Owner")
    client.post(URL, {"question": "first"})
    client.post(URL, {"action": "clear"})
    assert "first answer" not in client.get(URL).content.decode()


def test_switched_off_without_a_key(client_for, settings):
    settings.ASSISTANT_API_KEY = ""
    client = client_for("Owner")
    html = client.get(URL).content.decode()
    assert "switched off" in html and "data-ask-form" not in html
    response = client.post(URL, {"question": "hi"}, headers={"X-Requested-With": "fetch"})
    assert response.status_code == 503
