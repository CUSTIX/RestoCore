import pytest
from django.contrib.auth import get_user_model

from apps.staff.models import EmployeeProfile


@pytest.mark.django_db
def test_employee_profile_is_separate_from_auth_identity():
    user = get_user_model().objects.create_user(
        email="staff@example.com",
        password="test-only-password",
    )

    profile = EmployeeProfile.objects.create(
        user=user,
        employee_code="EMP-0001",
    )

    assert profile.user == user
    assert user.employee_profile == profile
    assert not hasattr(user, "employee_code")
