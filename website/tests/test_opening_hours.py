import datetime as dt

from bookings import selectors as bookings
from website.context_processors import CLOSING_TIME, is_open


def _minutes_from(base: dt.time, delta: int) -> dt.time:
    moment = dt.datetime.combine(dt.date(2026, 1, 1), base) + dt.timedelta(minutes=delta)
    return moment.time()


def test_open_exactly_at_opening_time_and_closed_a_minute_before():
    opening, _ = bookings.opening_hours()
    assert is_open(opening)
    assert not is_open(_minutes_from(opening, -1))


def test_closed_exactly_at_closing_time_and_open_a_minute_before():
    assert not is_open(CLOSING_TIME)
    assert is_open(_minutes_from(CLOSING_TIME, -1))


def test_closed_overnight():
    assert not is_open(dt.time(0, 0)) and not is_open(dt.time(3, 30))
