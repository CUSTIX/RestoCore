"""The assistant's read-only tools: right numbers, validated arguments, no contact details."""

import datetime as dt
import json
from decimal import Decimal

import pytest
from django.utils import timezone

from assistant import tools
from assistant.services import _json
from bookings.models import Booking
from sales import services as sales_services
from staff.models import LeaveRequest, Shift, TimeEntry

D = Decimal
pytestmark = pytest.mark.django_db


def today():
    return timezone.localdate()


@pytest.fixture
def sold(stocked_menu, make_user):
    """Two paid orders and one voided one today."""
    cashier = make_user("Cashier", first_name="Cara", last_name="Shier")

    def place(qty, method="cash"):
        return sales_services.place_order(
            quantities={stocked_menu["dish"].pk: qty},
            cashier=cashier,
            order_type="takeaway",
            payment_method=method,
            amount_tendered=D("1000") if method == "cash" else D("0"),
        )

    place(1)
    place(2, "card")
    voided = place(1)
    sales_services.void_order(voided, user=make_user("Manager"), reason="test")
    return stocked_menu


def test_every_tool_runs_on_an_empty_database_and_returns_json():
    for name in tools.TOOLS:
        args = {"period_id": 1} if name == "get_pay_period" else {}
        result = tools.run(name, args)
        json.loads(_json(result))  # serialisable


def test_declarations_describe_every_tool():
    names = {d["name"] for d in tools.declarations()}
    assert names == set(tools.TOOLS)
    assert all(d["description"] for d in tools.declarations())


def test_sales_report_adds_up(sold, settings):
    settings.SALES_TAX_RATE = "0.12"
    report = tools.run("sales_report", {"start_date": today().isoformat()})
    assert report["orders"] == 2
    assert report["revenue"] == D("336.00")  # (100 + 200) * 1.12
    assert report["voided_orders"] == 1
    assert {r["payment_method"] for r in report["by_payment_method"]} == {"cash", "card"}
    assert report["items"][0]["name"] == "Rice bowl" and report["items"][0]["qty"] == 3
    assert report["by_cashier"][0]["cashier"] == "Cara Shier"


def test_list_orders_shows_dishes_and_filters_status(sold):
    voided = tools.run("list_orders", {"status": "voided"})["orders"]
    assert len(voided) == 1 and voided[0]["void_reason"] == "test"
    assert voided[0]["items"] == ["1x Rice bowl"]
    assert len(tools.run("list_orders", {})["orders"]) == 3


def test_overview_and_inventory_reflect_stock(sold):
    inv = tools.run("get_inventory", {})
    rice = inv["items"][0]
    assert rice["quantity"] == D("9.4")  # 10 - 0.2 * 3 sold (the void returned its 0.2)
    assert rice["stock_value"] == D("470.00") and rice["low"] is False
    assert tools.run("get_overview", {})["sales_today"]["paid_orders"] == 2


def test_inventory_shortfall_and_restock_cost(stocked_menu):
    rice = stocked_menu["rice"]  # 10 kg on hand at 50 per kg
    type(rice).objects.filter(pk=rice.pk).update(reorder_level=D("12"))
    low = tools.run("get_inventory", {"low_only": True})
    assert low["items"][0]["low"] is True and low["items"][0]["shortfall"] == D("2")
    assert low["total_cost_to_reach_reorder_levels"] == D("100.00")


def test_stock_movements_cost_sales(sold):
    rows = tools.run("stock_movements", {"reason": "sale"})["rows"]
    assert rows and rows[0]["reason"] == "sale"
    assert rows[0]["cost"] == D("40.00")  # 0.8 kg used by 4 dishes ordered * 50


def test_bookings_tools_hide_contact_details(tomorrow):
    Booking.objects.create(
        name="Ann Guest",
        phone="09170000000",
        email="ann@example.com",
        party_size=4,
        date=tomorrow,
        time=dt.time(19, 0),
        notes="Window seat",
    )
    row = tools.run("list_bookings", {})["bookings"][0]
    assert row["guest"] == "Ann Guest" and row["notes"] == "Window seat"
    assert "phone" not in row and "email" not in row
    stats = tools.run(
        "booking_stats", {"start_date": tomorrow.isoformat(), "end_date": tomorrow.isoformat()}
    )
    assert stats["bookings"] == 1 and stats["expected_or_served_guests"] == 4


def test_no_show_rate():
    day = today() - dt.timedelta(days=1)
    for status in ("completed", "completed", "completed", "no_show"):
        Booking.objects.create(
            name="G", phone="1", party_size=2, date=day, time=dt.time(12), status=status
        )
    stats = tools.run("booking_stats", {"start_date": day.isoformat(), "end_date": day.isoformat()})
    assert stats["no_show_rate"] == 0.25


def test_staff_tools(make_employee, make_user):
    emp = make_employee(role="Cashier", rate=D("120"), phone="0999")
    emp.user.first_name, emp.user.last_name = "Pia", "Reyes"
    emp.user.save()
    Shift.objects.create(employee=emp, date=today(), start_time=dt.time(9), end_time=dt.time(17))
    start = timezone.now() - dt.timedelta(hours=5)
    TimeEntry.objects.create(employee=emp, clock_in=start, clock_out=start + dt.timedelta(hours=4))
    LeaveRequest.objects.create(
        employee=emp, leave_type="sick", start_date=today(), end_date=today(), reason="flu"
    )

    people = tools.run("list_employees", {})["employees"]
    assert people == [
        {
            "name": "Pia Reyes",
            "role": "Cashier",
            "position": "Cashier",
            "hourly_rate": D("120"),
            "hire_date": dt.date(2024, 1, 1),
            "active": True,
        }
    ]
    assert tools.run("get_schedule", {"employee": "pia"})["shifts"][0]["hours"] == 8
    assert tools.run("get_schedule", {"employee": "nobody"})["shifts"] == []
    worked = tools.run("get_attendance", {})["hours_worked"]
    assert worked == [{"employee": "Pia Reyes", "hours": D("4.00")}]
    leave = tools.run("list_leave", {"status": "pending"})["leave_requests"]
    assert leave[0]["employee"] == "Pia Reyes" and leave[0]["reason"] == "flu"


def test_payroll_tools(make_employee, make_user):
    from payroll import services as payroll_services

    emp = make_employee(rate=D("100"))
    start = today() - dt.timedelta(days=10)
    clock_in = timezone.make_aware(dt.datetime.combine(start, dt.time(9)))
    TimeEntry.objects.create(
        employee=emp, clock_in=clock_in, clock_out=clock_in + dt.timedelta(hours=8)
    )
    period = payroll_services.create_period(
        start_date=start, end_date=start + dt.timedelta(days=1), user=make_user("Owner")
    )
    payroll_services.generate_payslips(period)
    periods = tools.run("list_pay_periods", {})["periods"]
    assert periods[0]["id"] == period.pk and periods[0]["payslips"] == 1
    detail = tools.run("get_pay_period", {"period_id": period.pk})
    assert detail["payslips"][0]["hours"] == D("8.00")
    assert detail["payslips"][0]["gross"] == D("800.00")
    assert tools.run("get_pay_period", {"period_id": 99999}) == {
        "error": "No pay period with that id."
    }
    assert "error" in tools.run("get_pay_period", {"period_id": "abc"})


@pytest.mark.parametrize(
    "name,args,message",
    [
        ("sales_report", {"start_date": "yesterday"}, "not a date"),
        ("sales_report", {"start_date": "2026-05-02", "end_date": "2026-05-01"}, "before"),
        ("sales_report", {"start_date": "2020-01-01", "end_date": "2026-01-01"}, "at most"),
        ("get_schedule", {"start_date": "2026-01-01", "end_date": "2026-03-01"}, "at most 31"),
        ("list_bookings", {"status": "everything"}, "must be one of"),
        ("no_such_tool", {}, "no tool"),
    ],
)
def test_bad_arguments_come_back_as_errors_for_the_model(name, args, message):
    result = tools.run(name, args)
    assert message in result["error"]


def test_unexpected_arguments_are_ignored():
    assert "error" not in tools.run("get_menu", {"sql": "drop table"})
