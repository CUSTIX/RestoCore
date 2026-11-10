import pytest


@pytest.mark.django_db
def test_healthz_returns_ok(client):
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.content == b"ok"


def test_unknown_url_returns_404(client):
    response = client.get("/does-not-exist/")

    assert response.status_code == 404
