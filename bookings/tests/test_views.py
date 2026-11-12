import datetime as dt

import pytest

from bookings import services
from bookings.models import Booking
from bookings.tests.test_services import booking_data

ALLOWED = {"Owner": 200, "Manager": 200, "Staff": 200, "Cashier": 403, "Kitchen": 403}


def form_data(day, **overrides):
    data = {
        "name": "Ana Guest",
        "phone": "0917 111 2222",
        "email": "ana@example.com",
        "party_size": "2",
        "date": day.isoformat(),
        "time": "19:00",
        "notes": "",
        "website": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_public_booking_form_creates_pending_booking(client, tomorrow):
    response = client.post("/book/", form_data(tomorrow))
    booking = Booking.objects.get()
    assert response.status_code == 302
    assert response.url == f"/book/thanks/{booking.reference}/"
    assert booking.status == "pending" and booking.source == "website"
    assert "Ana Guest" in client.get(response.url).content.decode()


@pytest.mark.django_db
def test_public_booking_rejects_missing_phone(client, tomorrow):
    response = client.post("/book/", form_data(tomorrow, phone=""))
    assert response.status_code == 200
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_public_booking_honeypot_blocks_bots(client, tomorrow):
    client.post("/book/", form_data(tomorrow, website="http://spam.example"))
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_public_booking_shows_capacity_error(client, tomorrow):
    for _ in range(2):
        services.create_booking(**booking_data(tomorrow, party_size=20, time=dt.time(19, 0)))
    response = client.post("/book/", form_data(tomorrow))
    assert response.status_code == 200
    assert "fully booked" in response.content.decode()


@pytest.mark.django_db
def test_unknown_reference_returns_404(client):
    assert client.get("/book/thanks/NOPE1234/").status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", ALLOWED.items())
def test_booking_list_access_per_role(client_for, role, status):
    assert client_for(role).get("/app/bookings/").status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", ALLOWED.items())
def test_booking_status_change_access_per_role(client_for, tomorrow, role, status):
    b = services.create_booking(**booking_data(tomorrow))
    response = client_for(role).post(f"/app/bookings/{b.pk}/status/", {"status": "confirmed"})
    b.refresh_from_db()
    if status == 200:
        assert response.status_code == 302 and b.status == "confirmed"
    else:
        assert response.status_code == 403 and b.status == "pending"


@pytest.mark.django_db
def test_staff_can_create_phone_booking(client_for, tomorrow):
    c = client_for("Staff")
    data = form_data(tomorrow)
    data.pop("website")
    response = c.post("/app/bookings/new/", data)
    assert response.status_code == 302
    assert Booking.objects.get().source == "staff"


@pytest.mark.django_db
def test_booking_list_filters_by_status(client_for, tomorrow):
    services.create_booking(**booking_data(tomorrow, name="Pending Person"))
    b = services.create_booking(**booking_data(tomorrow, name="Confirmed Person"))
    services.change_status(b, "confirmed")
    html = client_for("Manager").get("/app/bookings/?status=confirmed").content.decode()
    assert "Confirmed Person" in html and "Pending Person" not in html


@pytest.mark.django_db
def test_public_bookings_are_rate_limited_per_visitor_ip(client, tomorrow):
    for _ in range(services.PUBLIC_BOOKINGS_PER_HOUR):
        assert (
            client.post("/book/", form_data(tomorrow), REMOTE_ADDR="203.0.113.50").status_code
            == 302
        )
    response = client.post("/book/", form_data(tomorrow), REMOTE_ADDR="203.0.113.50")
    assert response.status_code == 200
    assert "Please call us" in response.content.decode()
    assert Booking.objects.count() == services.PUBLIC_BOOKINGS_PER_HOUR
    # Someone else (another IP) can still book.
    assert (
        client.post("/book/", form_data(tomorrow), REMOTE_ADDR="198.51.100.60").status_code == 302
    )


@pytest.mark.django_db
def test_staff_phone_bookings_are_not_rate_limited(tomorrow):
    for _ in range(services.PUBLIC_BOOKINGS_PER_HOUR + 2):
        services.create_booking(source=Booking.Source.STAFF, **booking_data(tomorrow))
    assert Booking.objects.count() == services.PUBLIC_BOOKINGS_PER_HOUR + 2
