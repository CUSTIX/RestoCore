import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from bookings import services
from bookings.models import Booking

NOON = dt.time(12, 0)


def booking_data(day, **overrides):
    data = {
        "name": "Test Guest",
        "phone": "0917 000 0000",
        "email": "",
        "party_size": 4,
        "date": day,
        "time": NOON,
        "notes": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_create_booking_in_future_slot(tomorrow):
    booking = services.create_booking(**booking_data(tomorrow))
    assert booking.status == Booking.Status.PENDING
    assert len(booking.reference) == 8


@pytest.mark.django_db
def test_booking_in_the_past_is_rejected():
    yesterday = timezone.localdate() - dt.timedelta(days=1)
    with pytest.raises(ValidationError, match="already passed"):
        services.create_booking(**booking_data(yesterday))


@pytest.mark.django_db
def test_booking_outside_opening_hours_is_rejected(tomorrow):
    with pytest.raises(ValidationError, match="available times"):
        services.create_booking(**booking_data(tomorrow, time=dt.time(3, 0)))


@pytest.mark.django_db
def test_booking_too_far_ahead_is_rejected():
    far = timezone.localdate() + dt.timedelta(days=services.MAX_DAYS_AHEAD + 1)
    with pytest.raises(ValidationError, match="days ahead"):
        services.create_booking(**booking_data(far))


@pytest.mark.django_db
def test_slot_capacity_is_enforced(tomorrow):
    services.create_booking(**booking_data(tomorrow, party_size=20))
    services.create_booking(**booking_data(tomorrow, party_size=18))
    with pytest.raises(ValidationError, match="Only 2 seats"):
        services.create_booking(**booking_data(tomorrow, party_size=3))
    services.create_booking(**booking_data(tomorrow, party_size=2))  # exactly fills the slot
    with pytest.raises(ValidationError, match="fully booked"):
        services.create_booking(**booking_data(tomorrow, party_size=1))


@pytest.mark.django_db
def test_cancelled_bookings_free_their_seats(tomorrow):
    big = services.create_booking(**booking_data(tomorrow, party_size=20))
    services.create_booking(**booking_data(tomorrow, party_size=20))
    services.change_status(big, Booking.Status.CANCELLED)
    services.create_booking(**booking_data(tomorrow, party_size=20))


@pytest.mark.django_db
def test_valid_status_workflow(tomorrow):
    b = services.create_booking(**booking_data(tomorrow))
    b = services.change_status(b, "confirmed")
    # Guests are seated on the day itself: move the clock to the booking day.
    Booking.objects.filter(pk=b.pk).update(date=timezone.localdate())
    for status in ("seated", "completed"):
        b = services.change_status(b, status)
    assert b.status == "completed"


@pytest.mark.django_db
def test_invalid_transition_is_rejected(tomorrow):
    b = services.create_booking(**booking_data(tomorrow))
    with pytest.raises(ValidationError):
        services.change_status(b, Booking.Status.COMPLETED)  # pending → completed skips steps
    b = services.change_status(b, Booking.Status.CANCELLED)
    with pytest.raises(ValidationError):
        services.change_status(b, Booking.Status.CONFIRMED)  # cancelled is final


@pytest.mark.django_db
def test_closed_booking_cannot_be_edited(tomorrow):
    b = services.create_booking(**booking_data(tomorrow))
    b = services.change_status(b, Booking.Status.CANCELLED)
    with pytest.raises(ValidationError):
        services.update_booking(b, **booking_data(tomorrow, party_size=2))


@pytest.mark.django_db
def test_edit_does_not_count_own_seats_twice(tomorrow):
    b = services.create_booking(**booking_data(tomorrow, party_size=20))
    services.create_booking(**booking_data(tomorrow, party_size=20))  # slot now full (40)
    services.update_booking(b, **booking_data(tomorrow, party_size=20, name="Renamed"))
    b.refresh_from_db()
    assert b.name == "Renamed"
