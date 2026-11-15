import pytest

ENDPOINTS = [
    "/api/bookings/",
    "/api/inventory/low-stock/",
    "/api/sales/summary/",
    "/api/menu/",
    "/api/staff/on-shift/",
]
TOKEN = "test-token-abcdef-0123"


@pytest.fixture
def api_on(settings):
    settings.API_TOKEN = TOKEN
    return {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


@pytest.mark.django_db
@pytest.mark.parametrize("url", ENDPOINTS)
def test_api_disabled_without_token_setting(client, settings, url):
    settings.API_TOKEN = ""
    assert client.get(url).status_code == 503


@pytest.mark.django_db
@pytest.mark.parametrize("url", ENDPOINTS)
def test_api_rejects_missing_or_wrong_token(client, api_on, url):
    assert client.get(url).status_code == 401
    assert client.get(url, HTTP_AUTHORIZATION="Bearer wrong").status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("url", ENDPOINTS)
def test_api_returns_json_with_valid_token(client, api_on, url):
    response = client.get(url, **api_on)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ENDPOINTS)
def test_api_is_read_only(client, api_on, url):
    assert client.post(url, **api_on).status_code == 405


@pytest.mark.django_db
def test_api_rejects_bad_date(client, api_on):
    assert client.get("/api/bookings/?date=yesterday", **api_on).status_code == 400


@pytest.mark.django_db
def test_menu_endpoint_lists_available_items(client, api_on, stocked_menu):
    data = client.get("/api/menu/", **api_on).json()
    assert data["categories"][0]["items"][0] == {
        "name": "Rice bowl",
        "price": "100.00",
        "description": "",
    }


@pytest.mark.django_db
def test_repeated_wrong_tokens_lock_the_caller_out_even_for_the_right_one(client, api_on):
    """SEC-07: a guessing script gets 10 tries an hour, then nothing, including the real token."""
    for _ in range(10):
        assert client.get("/api/menu/", HTTP_AUTHORIZATION="Bearer wrong").status_code == 401
    assert client.get("/api/menu/", HTTP_AUTHORIZATION="Bearer wrong").status_code == 429
    assert client.get("/api/menu/", **api_on).status_code == 429


@pytest.mark.django_db
def test_requests_without_any_token_are_not_counted_as_guesses(client, api_on):
    for _ in range(15):
        assert client.get("/api/menu/").status_code == 401
    assert client.get("/api/menu/", **api_on).status_code == 200


@pytest.mark.django_db
def test_a_short_token_setting_switches_the_api_off(client, settings):
    """SEC-07: example tokens get copied into real deployments; refuse anything guessable."""
    settings.API_TOKEN = "short"
    response = client.get("/api/menu/", HTTP_AUTHORIZATION="Bearer short")
    assert response.status_code == 503 and "16" in response.json()["error"]
