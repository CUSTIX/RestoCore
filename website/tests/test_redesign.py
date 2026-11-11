from decimal import Decimal

import pytest

from sales.forms import MenuItemForm, dish_photo_choices
from sales.models import MenuItem
from sales.selectors import signature_dishes

PHOTO = "website/img/dishes/croissant.jpg"


@pytest.mark.django_db
def test_signature_dishes_come_first_then_top_up(stocked_menu):
    cat = stocked_menu["category"]
    star = MenuItem.objects.create(category=cat, name="Star", price=Decimal("5"), is_signature=True)
    picks = signature_dishes(limit=2)
    assert picks[0] == star and len(picks) == 2


def test_photo_choices_come_from_static_files():
    values = [v for v, _ in dish_photo_choices()]
    assert "" in values and PHOTO in values


@pytest.mark.django_db
def test_menu_item_form_rejects_unknown_photo(stocked_menu):
    data = {
        "category": stocked_menu["category"].pk,
        "name": "X",
        "price": "10",
        "photo": "../../etc/passwd",
        "is_available": "on",
    }
    form = MenuItemForm(data)
    assert not form.is_valid() and "photo" in form.errors


@pytest.mark.django_db
def test_home_shows_signature_dish_photo_and_currency(client, stocked_menu, settings):
    settings.CURRENCY_SYMBOL = "₱"
    dish = stocked_menu["dish"]
    dish.photo, dish.is_signature = PHOTO, True
    dish.save()
    html = client.get("/").content.decode()
    assert "dishes/croissant.jpg" in html and "₱100.00" in html


@pytest.mark.django_db
def test_menu_page_shows_item_without_photo_gracefully(client, stocked_menu):
    html = client.get("/menu/").content.decode()
    assert "menu-item__photo--empty" in html and "Rice bowl" in html
