import pytest
from django.contrib.auth import authenticate, get_user_model
from django.test import RequestFactory


def test_project_uses_email_based_custom_user_model():
    user_model = get_user_model()

    assert user_model._meta.label == "accounts.User"
    assert user_model._meta.db_table == "accounts_user"
    assert user_model.USERNAME_FIELD == "email"
    assert user_model._meta.get_field("email").unique is True
    assert "username" not in {field.name for field in user_model._meta.fields}


@pytest.mark.django_db
def test_user_can_authenticate_with_email():
    get_user_model().objects.create_user(
        email="manager@example.com",
        password="test-only-password",
    )

    request = RequestFactory().post("/login/")
    user = authenticate(
        request=request,
        email="manager@example.com",
        password="test-only-password",
    )

    assert user is not None
    assert user.email == "manager@example.com"
