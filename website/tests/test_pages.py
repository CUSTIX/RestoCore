import pytest


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/", "/menu/", "/book/", "/accounts/login/"])
def test_public_pages_render_for_anonymous_visitors(client, url):
    assert client.get(url).status_code == 200


def test_favicon_serves_svg(client):
    response = client.get("/favicon.svg")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("image/svg+xml")
    assert response.content.decode().lstrip().startswith("<svg")


def test_favicon_ico_redirects_to_svg(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301 and response["Location"] == "/favicon.svg"


def test_unknown_favicon_path_is_404(client):
    assert client.get("/favicon.png").status_code == 404


@pytest.mark.django_db
def test_pages_link_the_favicon(client):
    assert 'href="/favicon.svg"' in client.get("/").content.decode()


@pytest.mark.django_db
def test_menu_shows_available_items_only(client, stocked_menu):
    from sales.models import MenuItem

    MenuItem.objects.create(
        category=stocked_menu["category"], name="Secret dish", price=5, is_available=False
    )
    html = client.get("/menu/").content.decode()
    assert "Rice bowl" in html and "Secret dish" not in html
