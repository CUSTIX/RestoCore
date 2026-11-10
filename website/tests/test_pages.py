import pytest


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/", "/menu/", "/book/", "/accounts/login/"])
def test_public_pages_render_for_anonymous_visitors(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_menu_shows_available_items_only(client, stocked_menu):
    from sales.models import MenuItem

    MenuItem.objects.create(
        category=stocked_menu["category"], name="Secret dish", price=5, is_available=False
    )
    html = client.get("/menu/").content.decode()
    assert "Rice bowl" in html and "Secret dish" not in html
