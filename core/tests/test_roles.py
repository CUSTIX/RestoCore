import pytest
from django.contrib.auth.models import AnonymousUser, Group

from core.roles import ALL_ROLES, OWNER, has_role, user_roles


@pytest.mark.django_db
def test_role_groups_are_created_by_migration():
    assert set(Group.objects.values_list("name", flat=True)) >= set(ALL_ROLES)


@pytest.mark.django_db
def test_user_with_role_has_only_that_role(make_user):
    user = make_user("Cashier")
    assert user_roles(user) == {"Cashier"}
    assert has_role(user, "Cashier", "Manager")
    assert not has_role(user, "Manager")


@pytest.mark.django_db
def test_superuser_counts_as_owner(django_user_model):
    admin = django_user_model.objects.create_superuser("root", password="x")
    assert has_role(admin, OWNER)


def test_anonymous_has_no_roles():
    assert user_roles(AnonymousUser()) == set()


@pytest.mark.django_db
def test_user_without_role_cannot_use_staff_area(client, make_user):
    client.force_login(make_user(None))
    assert client.get("/app/").status_code == 403


@pytest.mark.django_db
def test_anonymous_is_redirected_to_login(client):
    response = client.get("/app/")
    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")
