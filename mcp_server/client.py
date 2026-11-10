"""Tiny HTTP client for the RestoCore read-only API. Standard library only.

Config (environment variables):
  RESTOCORE_API_URL    default http://127.0.0.1:8000
  RESTOCORE_API_TOKEN  required; must match the Django app's RESTOCORE_API_TOKEN
"""

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class RestoCoreError(RuntimeError):
    pass


class RestoCoreClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 10):
        self.base_url = base_url or os.environ.get("RESTOCORE_API_URL", "http://127.0.0.1:8000")
        self.base_url = self.base_url.rstrip("/")
        self.token = token if token is not None else os.environ.get("RESTOCORE_API_TOKEN", "")
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.token:
            raise RestoCoreError("RESTOCORE_API_TOKEN is not set.")
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        request = urllib.request.Request(
            f"{self.base_url}{path}{query}",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                message = json.loads(exc.read().decode()).get("error", exc.reason)
            except (ValueError, AttributeError):
                message = exc.reason
            raise RestoCoreError(f"RestoCore API error {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            message = f"Cannot reach RestoCore at {self.base_url}: {exc.reason}"
            raise RestoCoreError(message) from exc

    @staticmethod
    def _check_date(date: str | None) -> dict:
        if not date:
            return {}
        dt.date.fromisoformat(date)  # raises ValueError for bad input before any request
        return {"date": date}

    def bookings(self, date: str | None = None) -> dict:
        return self._get("/api/bookings/", self._check_date(date))

    def low_stock(self) -> dict:
        return self._get("/api/inventory/low-stock/")

    def sales_summary(self, date: str | None = None) -> dict:
        return self._get("/api/sales/summary/", self._check_date(date))

    def menu(self) -> dict:
        return self._get("/api/menu/")

    def on_shift(self) -> dict:
        return self._get("/api/staff/on-shift/")
