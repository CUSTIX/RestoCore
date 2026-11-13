"""The conversation loop, limits and answer formatting, with a scripted fake model."""

import io
import json
import urllib.error

import pytest

from assistant import llm, services
from assistant.llm import AssistantUnavailable

pytestmark = pytest.mark.django_db


class FakeModel:
    """Returns scripted model turns and records what it was sent."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls = []

    def generate(self, *, system, contents, tools):
        self.calls.append({"system": system, "contents": json.loads(json.dumps(contents))})
        return self.turns.pop(0)


def call(name, **args):
    return {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}}]}


def text(value):
    return {"role": "model", "parts": [{"text": value}]}


@pytest.fixture
def owner(make_user):
    return make_user("Owner")


@pytest.fixture
def session():
    return {}


def test_tool_results_go_back_to_the_model_and_the_answer_comes_out(owner, session, stocked_menu):
    fake = FakeModel(call("get_menu"), text("You have **1** dish: Rice bowl."))
    answer = services.ask("What's on the menu?", user=owner, session=session, client=fake)
    assert answer.text == "You have **1** dish: Rice bowl."
    assert answer.sources == ["Menu"]
    sent = fake.calls[1]["contents"]
    response = sent[-1]["parts"][0]["functionResponse"]
    assert response["name"] == "get_menu"
    assert response["response"]["items"][0]["name"] == "Rice bowl"
    assert sent[-2] == call("get_menu")  # the model's own turn is echoed back unchanged


def test_system_prompt_gives_the_date_and_treats_data_as_untrusted(owner, session):
    fake = FakeModel(text("ok"))
    services.ask("hi", user=owner, session=session, client=fake)
    system = fake.calls[0]["system"]
    assert "Now:" in system and "never instructions" in system


def test_several_tool_calls_in_one_turn(owner, session):
    both = {
        "role": "model",
        "parts": [
            {"functionCall": {"name": "sales_report", "args": {"start_date": "2026-01-01"}}},
            {"functionCall": {"name": "get_inventory", "args": {}}},
        ],
    }
    fake = FakeModel(both, text("done"))
    answer = services.ask("sales and stock?", user=owner, session=session, client=fake)
    assert answer.sources == ["Sales report", "Inventory"]
    assert len(fake.calls[1]["contents"][-1]["parts"]) == 2


def test_a_bad_tool_call_is_reported_to_the_model_not_raised(owner, session):
    fake = FakeModel(call("drop_tables"), call("sales_report", start_date="nope"), text("sorry"))
    assert services.ask("x", user=owner, session=session, client=fake).text == "sorry"
    errors = [c["contents"][-1]["parts"][0]["functionResponse"]["response"] for c in fake.calls[1:]]
    assert "no tool" in errors[0]["error"] and "not a date" in errors[1]["error"]


def test_history_is_sent_and_kept_short(owner, session):
    for i in range(services.HISTORY_TURNS + 2):
        services.ask(f"q{i}", user=owner, session=session, client=FakeModel(text(f"a{i}")))
    assert len(services.history(session)) == services.HISTORY_TURNS
    fake = FakeModel(text("last"))
    services.ask("follow-up", user=owner, session=session, client=fake)
    contents = fake.calls[0]["contents"]
    assert contents[-1]["parts"][0]["text"] == "follow-up"
    assert contents[-2] == {
        "role": "model",
        "parts": [{"text": services.history(session)[-2]["a"]}],
    }
    services.clear_history(session)
    assert services.history(session) == []


def test_endless_tool_loops_stop(owner, session):
    fake = FakeModel(*[call("get_menu")] * services.MAX_TOOL_ROUNDS)
    with pytest.raises(AssistantUnavailable, match="too many steps"):
        services.ask("loop", user=owner, session=session, client=fake)


def test_hourly_and_daily_limits(owner, session, settings, make_user):
    settings.ASSISTANT_HOURLY_LIMIT = 2
    for _ in range(2):
        services.ask("q", user=owner, session=session, client=FakeModel(text("a")))
    with pytest.raises(AssistantUnavailable, match="this hour"):
        services.ask("q", user=owner, session=session, client=FakeModel(text("a")))
    settings.ASSISTANT_HOURLY_LIMIT, settings.ASSISTANT_DAILY_LIMIT = 50, 2
    with pytest.raises(AssistantUnavailable, match="today"):
        services.ask("q", user=make_user("Owner"), session={}, client=FakeModel(text("a")))


def test_empty_questions_and_missing_key(owner, session, settings):
    with pytest.raises(AssistantUnavailable, match="Type a question"):
        services.ask("   ", user=owner, session=session, client=FakeModel())
    settings.ASSISTANT_API_KEY = ""
    with pytest.raises(AssistantUnavailable, match="GEMINI_API_KEY"):
        services.ask("hi", user=owner, session=session)


def test_thoughts_are_not_shown(owner, session):
    turn = {"role": "model", "parts": [{"text": "secret plan", "thought": True}, {"text": "Hi!"}]}
    assert services.ask("hi", user=owner, session=session, client=FakeModel(turn)).text == "Hi!"


# ---- Gemini client error mapping -------------------------------------------------------------


@pytest.mark.parametrize(
    "code,message", [(429, "quota"), (403, "API key"), (404, "model"), (500, "problem")]
)
def test_http_errors_become_friendly_messages(monkeypatch, code, message):
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b""))

    monkeypatch.setattr(llm.urllib.request, "urlopen", fail)
    with pytest.raises(AssistantUnavailable, match=message):
        llm.GeminiClient(api_key="k", model="gemini-test").generate(
            system="", contents=[], tools=[]
        )


def test_an_invalid_key_reported_as_400_is_named(monkeypatch):
    body = io.BytesIO(b'{"error": {"status": "INVALID_ARGUMENT", "details": ["API_KEY_INVALID"]}}')

    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("u", 400, "x", {}, body)

    monkeypatch.setattr(llm.urllib.request, "urlopen", fail)
    with pytest.raises(AssistantUnavailable, match="API key"):
        llm.GeminiClient(api_key="k", model="gemini-test").generate(
            system="", contents=[], tools=[]
        )


def test_client_sends_the_key_in_a_header_not_the_url(monkeypatch):
    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        seen["url"], seen["headers"] = request.full_url, dict(request.header_items())
        return Response(json.dumps({"candidates": [{"content": text("hi")}]}).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    out = llm.GeminiClient(api_key="secret-k", model="gemini-test").generate(
        system="s", contents=[], tools=[]
    )
    assert out == text("hi")
    assert "secret-k" not in seen["url"] and seen["headers"]["X-goog-api-key"] == "secret-k"


def test_model_names_are_validated():
    with pytest.raises(AssistantUnavailable):
        llm.GeminiClient(api_key="k", model="../../evil?x=")


# ---- formatting ------------------------------------------------------------------------------


def test_format_answer_paragraphs_bullets_and_bold():
    blocks = services.format_answer(
        "Sales are **up**.\nNice week.\n\n- Lattes: **42**\n* Toast\n1. Third"
        "\n\n## Tip\nOrder rice."
    )
    assert blocks[0] == {
        "type": "p",
        "runs": [
            {"text": "Sales are "},
            {"text": "up", "bold": True},
            {"text": "."},
            {"text": " "},
            {"text": "Nice week."},
        ],
    }
    assert blocks[1]["type"] == "ul" and len(blocks[1]["items"]) == 3
    assert blocks[1]["items"][0] == [{"text": "Lattes: "}, {"text": "42", "bold": True}]
    assert blocks[2] == {
        "type": "p",
        "runs": [{"text": "Tip"}, {"text": " "}, {"text": "Order rice."}],
    }


def test_unbalanced_markup_never_leaks_asterisks():
    assert services.format_answer("a **b") == [{"type": "p", "runs": [{"text": "a b"}]}]
