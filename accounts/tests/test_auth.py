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
@pytest.mark.parametrize(
    "debug,demo_mode,shown",
    [(True, False, True), (False, False, False), (False, True, True)],
)
def test_demo_logins_shown_in_debug_or_public_demo_mode(client, settings, debug, demo_mode, shown):
    settings.DEBUG = debug
    settings.DEMO_MODE = demo_mode
    html = client.get("/accounts/login/").content.decode()
    assert ("Demo accounts" in html) is shown
    assert ("restocore-demo" in html) is shown  # never leak the password otherwise


@pytest.mark.django_db
def test_password_change_page_requires_login(client):
    assert client.get("/accounts/password/").status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize(
    "next_url,expected",
    [
        ("/app/sales/orders/", "/app/sales/orders/"),  # a page on this site: honoured
        ("https://evil.example/phish", "/app/"),  # another site: ignored
        ("//evil.example/phish", "/app/"),  # protocol-relative: ignored
        ("javascript:alert(1)", "/app/"),
    ],
)
def test_login_only_follows_next_urls_on_this_site(client, make_user, next_url, expected):
    user = make_user("Owner")
    response = client.post(
        "/accounts/login/", {"username": user.username, "password": PASSWORD, "next": next_url}
    )
    assert response.status_code == 302 and response.url == expected


@pytest.mark.django_db
def test_password_change_succeeds_and_the_new_password_works(client, make_user):
    user = make_user("Staff")
    client.force_login(user)
    response = client.post(
        "/accounts/password/",
        {
            "old_password": PASSWORD,
            "new_password1": "a-much-longer-new-pass-42",
            "new_password2": "a-much-longer-new-pass-42",
        },
    )
    assert response.status_code == 302
    client.logout()
    assert client.login(username=user.username, password="a-much-longer-new-pass-42")
    assert not client.login(username=user.username, password=PASSWORD)


@pytest.mark.django_db
def test_password_change_rejects_a_wrong_current_password(client, make_user):
    user = make_user("Staff")
    client.force_login(user)
    response = client.post(
        "/accounts/password/",
        {
            "old_password": "wrong",
            "new_password1": "x-new-pass-12345",
            "new_password2": "x-new-pass-12345",
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
