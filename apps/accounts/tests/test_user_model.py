from django.contrib.auth import get_user_model


def test_project_uses_custom_user_model():
    user_model = get_user_model()

    assert user_model._meta.label == "accounts.User"
    assert user_model._meta.db_table == "accounts_user"
    assert user_model._meta.get_field("email").unique is True
