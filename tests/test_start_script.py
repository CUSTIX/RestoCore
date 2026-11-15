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


@pytest.mark.parametrize("bad", ["abc", "25", "-1", "4.5", ""])
def test_the_cli_rejects_an_invalid_hour_with_a_clean_error(bad):
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [sys.executable, str(_PATH), bad], capture_output=True, text=True, env={"PATH": ""}
    )
    assert result.returncode != 0 and "Traceback" not in result.stderr
    assert "0-23" in result.stderr


def test_the_cli_prints_whole_seconds_for_a_valid_hour():
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [sys.executable, str(_PATH), "4"], capture_output=True, text=True
    )
    assert result.returncode == 0 and 0 < int(result.stdout) <= 24 * 3600 + 1
