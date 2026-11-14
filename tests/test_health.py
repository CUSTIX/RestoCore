import pytest


@pytest.mark.django_db
def test_healthz_returns_ok(client):
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.content == b"ok"


def test_unknown_url_returns_404(client):
    response = client.get("/does-not-exist/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_livez_answers_without_touching_the_database(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = client.get("/livez/")

    assert response.status_code == 200
    assert response.content == b"ok"


def test_livez_sets_no_cookies(client):
    # A ping every 10 minutes must not create sessions or CSRF cookies.
    response = client.get("/livez/")

    assert not response.cookies
