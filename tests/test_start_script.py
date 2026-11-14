import datetime as dt
import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "bin" / "seconds_until_hour.py"
_spec = importlib.util.spec_from_file_location("seconds_until_hour", _PATH)
seconds_until_hour = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seconds_until_hour)

TZ = dt.timezone(dt.timedelta(hours=8))


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (dt.datetime(2026, 11, 14, 3, 0, tzinfo=TZ), 3600 + 1),  # later today
        (dt.datetime(2026, 11, 14, 4, 0, tzinfo=TZ), 24 * 3600 + 1),  # exactly now: tomorrow
        (dt.datetime(2026, 11, 14, 21, 30, tzinfo=TZ), 6 * 3600 + 1800 + 1),  # tomorrow
    ],
)
def test_seconds_until_next_reset_hour(now, expected):
    assert seconds_until_hour.seconds_until_hour(4, now) == expected
