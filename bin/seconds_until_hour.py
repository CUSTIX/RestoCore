"""Print the seconds until the next HOUR:00 in the app's time zone (used by bin/start.sh).

Usage: python bin/seconds_until_hour.py 4
"""

import datetime as dt
import os
import sys
import zoneinfo


def seconds_until_hour(hour, now):
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return int((target - now).total_seconds()) + 1


if __name__ == "__main__":
    hour = int(sys.argv[1])
    if not 0 <= hour <= 23:
        sys.exit("hour must be 0-23")
    tz = zoneinfo.ZoneInfo(os.environ.get("DJANGO_TIME_ZONE", "UTC"))
    print(seconds_until_hour(hour, dt.datetime.now(tz)))
