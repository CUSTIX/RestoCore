"""Status changes, edits, lists and availability must respect the booking's date and time."""

import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from bookings import selectors, services
from bookings.models import Booking

S = Booking.Status
NOW = dt.datetime(2026, 6, 10, 15, 0)  # a fixed "now" for the pure rule tests


def b(day_offset=0, at=dt.time(19, 0), status=S.CONFIRMED):
    return Booking(date=NOW.date() + dt.timedelta(days=day_offset), time=at, status=status)


@pytest.mark.parametrize(
    "booking,expected",
    [
        # pending: confirm only while the time is still ahead
        (b(1, status=S.PENDING), {S.CONFIRMED, S.CANCELLED}),
        (b(-1, status=S.PENDING), {S.CANCELLED}),
        # confirmed next week: can't be seated or a no-show yet
        (b(7), {S.CANCELLED}),
        # confirmed later today: seat them today, but not a no-show yet
        (b(0, at=dt.time(19, 0)), {S.SEATED, S.CANCELLED}),
        # confirmed earlier today, time passed: seat (they're late) or no-show
        (b(0, at=dt.time(12, 0)), {S.SEATED, S.CANCELLED, S.NO_SHOW}),
        # confirmed yesterday, never closed: no-show or cancel, not seat
        (b(-1), {S.CANCELLED, S.NO_SHOW}),
        (b(0, status=S.SEATED), {S.COMPLETED}),
    ],
)
def test_transitions_follow_the_clock(booking, expected):
    assert set(services.allowed_transitions(booking, now=NOW)) == expected


def make(days, at, status=S.CONFIRMED, party=2, name="Guest"):
    return Booking.objects.create(
        name=name,
        phone="0917 000 0000",
        party_size=party,
        date=timezone.localdate() + dt.timedelta(days=days),
        time=at,
        status=status,
    )


@pytest.mark.django_db
def test_seating_next_weeks_booking_is_refused_with_a_clear_reason():
    booking = make(7, dt.time(19, 0))
    with pytest.raises(ValidationError, match="on the day of the booking"):
        services.change_status(booking, S.SEATED)


@pytest.mark.django_db
def test_no_show_before_the_time_is_refused():
    booking = make(3, dt.time(19, 0))
    with pytest.raises(ValidationError, match="once the booking time has passed"):
        services.change_status(booking, S.NO_SHOW)


@pytest.mark.django_db
def test_clicking_the_same_status_twice_is_not_an_error():
    booking = make(3, dt.time(19, 0), status=S.PENDING)
    services.change_status(booking, S.CONFIRMED)
    assert services.change_status(booking, S.CONFIRMED).status == S.CONFIRMED


@pytest.mark.django_db
def test_contact_details_can_be_fixed_after_the_booking_time():
    booking = make(-1, dt.time(19, 0))
    data = {
        "name": "Guest",
        "phone": "0999 123 4567",
        "email": "",
        "party_size": 2,
        "date": booking.date,
        "time": booking.time,
        "notes": "",
    }
    services.update_booking(booking, **data)
    booking.refresh_from_db()
    assert booking.phone == "0999 123 4567"


@pytest.mark.django_db
def test_moving_a_booking_into_the_past_is_still_refused():
    booking = make(2, dt.time(19, 0))
    data = {"name": "G", "phone": "1", "email": "", "party_size": 2, "notes": ""}
    with pytest.raises(ValidationError, match="already passed"):
        services.update_booking(
            booking, date=timezone.localdate() - dt.timedelta(days=1), time=dt.time(19, 0), **data
        )


@pytest.mark.django_db
def test_growing_a_party_still_checks_seats_left():
    make(2, dt.time(19, 0), party=services.SLOT_CAPACITY - 4, name="Big group")
    booking = make(2, dt.time(19, 0), party=2)
    data = {"name": "G", "phone": "1", "email": "", "notes": "", "date": booking.date}
    with pytest.raises(ValidationError, match="seats are left"):
        services.update_booking(booking, time=booking.time, party_size=10, **data)


@pytest.mark.django_db
def test_list_defaults_to_upcoming_and_past_is_newest_first():
    old = make(-3, dt.time(12, 0), name="Old")
    older = make(-5, dt.time(12, 0), name="Older")
    soon = make(1, dt.time(12, 0), name="Soon")
    assert list(selectors.filter_bookings()) == [soon]
    assert list(selectors.filter_bookings(when="past")) == [old, older]


@pytest.mark.django_db
def test_to_confirm_counts_only_requests_that_can_still_be_confirmed():
    make(-1, dt.time(19, 0), status=S.PENDING)
    make(2, dt.time(19, 0), status=S.PENDING)
    assert selectors.today_summary()["pending"] == 1


@pytest.mark.django_db
def test_dashboard_upcoming_skips_finished_and_past_bookings():
    make(-1, dt.time(19, 0))
    make(1, dt.time(19, 0), status=S.COMPLETED)
    ahead = make(1, dt.time(20, 0))
    assert list(selectors.upcoming()) == [ahead]


@pytest.mark.django_db
def test_availability_counts_seats_and_hides_nothing_on_future_days(client):
    day = timezone.localdate() + dt.timedelta(days=2)
    make(2, dt.time(19, 0), party=services.SLOT_CAPACITY)  # 19:00 full
    data = client.get(f"/book/availability/?date={day.isoformat()}").json()
    assert data["seats"]["19:00"] == 0
    assert data["seats"]["18:00"] == services.SLOT_CAPACITY


@pytest.mark.django_db
def test_availability_marks_past_days_as_passed_and_rejects_bad_dates(client):
    yesterday = (timezone.localdate() - dt.timedelta(days=1)).isoformat()
    assert set(client.get(f"/book/availability/?date={yesterday}").json()["seats"].values()) == {
        None
    }
    assert client.get("/book/availability/?date=nope").status_code == 400


@pytest.mark.django_db
def test_editing_a_closed_booking_redirects_instead_of_showing_a_dead_form(client_for):
    booking = make(-1, dt.time(19, 0), status=S.COMPLETED)
    response = client_for("Manager").get(f"/app/bookings/{booking.pk}/edit/")
    assert response.status_code == 302 and response["Location"] == f"/app/bookings/{booking.pk}/"


@pytest.mark.django_db
def test_edit_form_allows_the_bookings_own_past_date(client_for):
    booking = make(-1, dt.time(19, 0))
    html = client_for("Manager").get(f"/app/bookings/{booking.pk}/edit/").content.decode()
    assert f'min="{timezone.localdate().isoformat()}"' not in html


@pytest.mark.django_db
def test_a_seated_booking_left_open_from_yesterday_is_not_upcoming():
    stale = make(-1, dt.time(19, 0), status=S.SEATED)
    assert stale not in selectors.filter_bookings()
    assert stale in selectors.filter_bookings(when="past")
    assert stale not in selectors.upcoming()
