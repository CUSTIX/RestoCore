from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.staff.models import AttendanceSession, BreakSession, EmployeeProfile, Shift


@pytest.fixture
def employee():
    user = get_user_model().objects.create_user(
        email="employee@example.com",
        password="test-only-password",
    )
    return EmployeeProfile.objects.create(user=user, employee_code="EMP-1001")


@pytest.mark.django_db
def test_shift_requires_end_after_start(employee):
    start = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        Shift.objects.create(
            employee=employee,
            starts_at=start,
            ends_at=start - timedelta(minutes=1),
        )


@pytest.mark.django_db
def test_only_one_open_attendance_session_per_employee(employee):
    now = timezone.now()
    AttendanceSession.objects.create(employee=employee, clock_in_at=now)

    with pytest.raises(IntegrityError), transaction.atomic():
        AttendanceSession.objects.create(
            employee=employee,
            clock_in_at=now + timedelta(minutes=1),
        )


@pytest.mark.django_db
def test_attendance_clock_out_must_follow_clock_in(employee):
    now = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        AttendanceSession.objects.create(
            employee=employee,
            clock_in_at=now,
            clock_out_at=now,
        )


@pytest.mark.django_db
def test_only_one_open_break_per_attendance(employee):
    attendance = AttendanceSession.objects.create(
        employee=employee,
        clock_in_at=timezone.now(),
    )
    BreakSession.objects.create(
        attendance=attendance,
        started_at=timezone.now(),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        BreakSession.objects.create(
            attendance=attendance,
            started_at=timezone.now() + timedelta(minutes=1),
        )
