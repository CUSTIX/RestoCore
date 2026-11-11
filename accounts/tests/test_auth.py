import pytest
from django.contrib.auth import get_user_model

from accounts.services import create_user_with_role, set_user_role
from conftest import PASSWORD
from core.roles import user_roles


def test_custom_user_model_is_used():
    assert get_user_model()._meta.label == "accounts.User"


@pytest.mark.django_db
def test_login_with_valid_credentials_redirects_to_dashboard(client, make_user):
    user = make_user("Staff")
    response = client.post("/accounts/login/", {"username": user.username, "password": PASSWORD})
    assert response.status_code == 302
    assert response.url == "/app/"


@pytest.mark.django_db
def test_login_with_wrong_password_fails(client, make_user):
    user = make_user("Staff")
    response = client.post("/accounts/login/", {"username": user.username, "password": "nope"})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_logout_requires_post_and_logs_out(client, make_user):
    client.force_login(make_user("Staff"))
    assert client.get("/accounts/logout/").status_code == 405
    response = client.post("/accounts/logout/")
    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_create_user_with_unknown_role_is_rejected():
    with pytest.raises(ValueError):
        create_user_with_role(username="x", password=PASSWORD, role="Wizard")


@pytest.mark.django_db
def test_set_user_role_replaces_previous_role(make_user):
    user = make_user("Staff")
    set_user_role(user, "Cashier")
    user = get_user_model().objects.get(pk=user.pk)  # fresh object: no cached roles
    assert user_roles(user) == {"Cashier"}


@pytest.mark.django_db
@pytest.mark.parametrize("debug,shown", [(True, True), (False, False)])
def test_demo_logins_only_shown_in_debug(client, settings, debug, shown):
    settings.DEBUG = debug
    html = client.get("/accounts/login/").content.decode()
    assert ("Demo accounts" in html) is shown


@pytest.mark.django_db
def test_password_change_page_requires_login(client):
    assert client.get("/accounts/password/").status_code == 302
