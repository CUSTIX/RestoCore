import pytest

ENDPOINTS = [
    "/api/bookings/",
    "/api/inventory/low-stock/",
    "/api/sales/summary/",
    "/api/menu/",
    "/api/staff/on-shift/",
]
TOKEN = "test-token-abc"


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
