"""The MCP tools are thin wrappers, so we test the client they call, end to end against Django."""

import io
import json
import urllib.error
from unittest import mock

import pytest

from mcp_server.client import RestoCoreClient, RestoCoreError


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def django_backed_urlopen(client):
    """Route urllib requests to the Django test client so we exercise the real API views."""

    def _urlopen(request, timeout=None):
        path = request.full_url.replace("http://testserver", "")
        response = client.get(path, HTTP_AUTHORIZATION=request.headers["Authorization"])
        if response.status_code >= 400:
            raise urllib.error.HTTPError(
                request.full_url, response.status_code, "error", {}, io.BytesIO(response.content)
            )
        return FakeResponse(response.content)

    return _urlopen


@pytest.fixture
def api(settings, client):
    settings.API_TOKEN = "mcp-test-token"
    with mock.patch("urllib.request.urlopen", django_backed_urlopen(client)):
        yield RestoCoreClient(base_url="http://testserver", token="mcp-test-token")


@pytest.mark.django_db
def test_menu_tool_reads_real_api(api, stocked_menu):
    assert api.menu()["categories"][0]["items"][0]["name"] == "Rice bowl"


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["bookings", "low_stock", "sales_summary", "on_shift"])
def test_every_tool_returns_json(api, method):
    assert isinstance(getattr(api, method)(), dict)


@pytest.mark.django_db
def test_wrong_token_raises_clear_error(settings, client):
    settings.API_TOKEN = "right"
    with mock.patch("urllib.request.urlopen", django_backed_urlopen(client)):
        bad = RestoCoreClient(base_url="http://testserver", token="wrong")
        with pytest.raises(RestoCoreError, match="401"):
            bad.menu()


def test_missing_token_fails_before_any_request():
    with pytest.raises(RestoCoreError, match="not set"):
        RestoCoreClient(token="").menu()


def test_bad_date_rejected_locally():
    with pytest.raises(ValueError):
        RestoCoreClient(token="x").bookings("tomorrow")


def test_unreachable_server_gives_friendly_error():
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(RestoCoreError, match="Cannot reach"):
            RestoCoreClient(token="x").low_stock()


def test_response_is_parsed_as_json():
    payload = json.dumps({"items": []}).encode()
    with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
        assert RestoCoreClient(token="x").low_stock() == {"items": []}
