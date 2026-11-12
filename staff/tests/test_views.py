import pytest

from staff.models import LeaveRequest, TimeEntry

MANAGE = {"Owner": 200, "Manager": 200, "Cashier": 403, "Kitchen": 403, "Staff": 403}
EVERYONE = {"Owner": 200, "Manager": 200, "Cashier": 200, "Kitchen": 200, "Staff": 200}


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", EVERYONE.items())
def test_my_work_page_for_every_role(client_for, make_employee, make_user, role, status):
    user = make_user(role)
    make_employee(user=user)
    assert client_for(user=user).get("/app/staff/me/").status_code == status


@pytest.mark.django_db
def test_my_work_without_employee_profile_still_renders(client_for):
    response = client_for("Staff").get("/app/staff/me/")
    assert response.status_code == 200
    assert "employee profile" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    ["/app/staff/employees/", "/app/staff/shifts/", "/app/staff/attendance/", "/app/staff/leave/"],
)
@pytest.mark.parametrize("role,status", MANAGE.items())
def test_management_pages_access_per_role(client_for, url, role, status):
    assert client_for(role).get(url).status_code == status


@pytest.mark.django_db
def test_clock_in_and_out_through_view(client_for, make_employee, make_user):
    user = make_user("Cashier")
    emp = make_employee(user=user)
    c = client_for(user=user)
    c.post("/app/staff/me/clock/", {"action": "in"})
    assert TimeEntry.objects.filter(employee=emp, clock_out__isnull=True).exists()
    c.post("/app/staff/me/clock/", {"action": "out"})
    assert not TimeEntry.objects.filter(employee=emp, clock_out__isnull=True).exists()


@pytest.mark.django_db
def test_clock_without_profile_is_forbidden(client_for):
    assert client_for("Staff").post("/app/staff/me/clock/", {"action": "in"}).status_code == 403


@pytest.mark.django_db
def test_leave_request_and_manager_approval(client_for, make_employee, make_user, tomorrow, client):
    staff_user = make_user("Staff")
    make_employee(user=staff_user)
    client.force_login(staff_user)
    client.post(
        "/app/staff/me/",
        {
            "leave_type": "vacation",
            "start_date": tomorrow.isoformat(),
            "end_date": tomorrow.isoformat(),
            "reason": "rest",
        },
    )
    leave = LeaveRequest.objects.get()
    assert leave.status == "pending"

    client.force_login(make_user("Manager"))
    client.post(f"/app/staff/leave/{leave.pk}/review/", {"decision": "approve", "note": "ok"})
    leave.refresh_from_db()
    assert leave.status == "approved"


@pytest.mark.django_db
def test_leave_list_defaults_to_pending_on_every_page(client_for, make_employee, tomorrow):
    emp = make_employee()
    LeaveRequest.objects.create(
        employee=emp,
        leave_type="sick",
        start_date=tomorrow,
        end_date=tomorrow,
        reason="pending-one",
    )
    LeaveRequest.objects.create(
        employee=emp,
        leave_type="sick",
        start_date=tomorrow,
        end_date=tomorrow,
        status="rejected",
        reason="rejected-one",
    )
    c = client_for("Manager")
    for url in ("/app/staff/leave/", "/app/staff/leave/?page=1"):
        html = c.get(url).content.decode()
        assert "pending-one" in html and "rejected-one" not in html
    html = c.get("/app/staff/leave/?status=").content.decode()
    assert "pending-one" in html and "rejected-one" in html


@pytest.mark.django_db
def test_staff_cannot_review_leave(client_for, make_employee, tomorrow):
    emp = make_employee()
    leave = LeaveRequest.objects.create(
        employee=emp, leave_type="sick", start_date=tomorrow, end_date=tomorrow
    )
    response = client_for("Staff").post(
        f"/app/staff/leave/{leave.pk}/review/", {"decision": "approve"}
    )
    assert response.status_code == 403
    leave.refresh_from_db()
    assert leave.status == "pending"


@pytest.mark.django_db
def test_user_cannot_cancel_someone_elses_leave(client_for, make_employee, make_user, tomorrow):
    other = make_employee()
    leave = LeaveRequest.objects.create(
        employee=other, leave_type="sick", start_date=tomorrow, end_date=tomorrow
    )
    me = make_user("Staff")
    make_employee(user=me)
    response = client_for(user=me).post(f"/app/staff/me/leave/{leave.pk}/cancel/")
    assert response.status_code == 403
    leave.refresh_from_db()
    assert leave.status == "pending"


@pytest.mark.django_db
def test_manager_creates_employee_via_form(client_for):
    data = {
        "username": "newcook",
        "password": "Str0ng-pass-word",
        "first_name": "New",
        "last_name": "Cook",
        "email": "",
        "role": "Kitchen",
        "position": "Cook",
        "phone": "",
        "hourly_rate": "120",
        "hire_date": "2024-05-01",
        "is_active": "on",
    }
    response = client_for("Manager").post("/app/staff/employees/new/", data)
    assert response.status_code == 302


@pytest.mark.django_db
def test_manager_cannot_create_owner_via_form(client_for):
    data = {
        "username": "boss2",
        "password": "Str0ng-pass-word",
        "first_name": "B",
        "last_name": "C",
        "email": "",
        "role": "Owner",
        "position": "Owner",
        "phone": "",
        "hourly_rate": "0",
        "hire_date": "2024-05-01",
        "is_active": "on",
    }
    response = client_for("Manager").post("/app/staff/employees/new/", data)
    assert response.status_code == 200
    assert "Only an owner" in response.content.decode()


@pytest.mark.django_db
def test_shift_create_via_form(client_for, make_employee, tomorrow):
    emp = make_employee()
    response = client_for("Manager").post(
        "/app/staff/shifts/new/",
        {
            "employee": emp.pk,
            "date": tomorrow.isoformat(),
            "start_time": "09:00",
            "end_time": "17:00",
            "note": "",
        },
    )
    assert response.status_code == 302
    assert emp.shifts.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("target_role", ["Owner", "Manager"])
def test_manager_cannot_edit_an_owner_or_another_manager(client_for, make_employee, target_role):
    """Privilege escalation guard: a manager must not demote, deactivate or rename the people
    above or beside them, even by posting the edit form directly."""
    target = make_employee(role=target_role)
    client = client_for("Manager")
    url = f"/app/staff/employees/{target.pk}/edit/"
    assert client.get(url).status_code == 403
    response = client.post(
        url,
        {
            "first_name": "Hacked",
            "last_name": "X",
            "email": "",
            "role": "Staff",
            "position": "x",
            "phone": "",
            "hourly_rate": "1",
            "hire_date": "2024-01-01",
            "is_active": "",
        },
    )
    assert response.status_code == 403
    target.user.refresh_from_db()
    assert target.user.is_active and target.user.first_name != "Hacked"
    assert target.user.groups.filter(name=target_role).exists()


@pytest.mark.django_db
def test_manager_can_edit_a_staff_member(client_for, make_employee):
    target = make_employee(role="Staff")
    assert client_for("Manager").get(f"/app/staff/employees/{target.pk}/edit/").status_code == 200


@pytest.mark.django_db
def test_employee_list_links_only_the_people_you_may_edit(client_for, make_employee):
    owner, staff = make_employee(role="Owner"), make_employee(role="Staff")
    html = client_for("Manager").get("/app/staff/employees/").content.decode()
    assert f"/app/staff/employees/{staff.pk}/edit/" in html
    assert f"/app/staff/employees/{owner.pk}/edit/" not in html


@pytest.mark.django_db
def test_employee_list_query_count_does_not_grow_per_row(
    client_for, make_employee, django_assert_max_num_queries
):
    client = client_for("Owner")
    for role in ["Staff", "Cashier", "Kitchen", "Manager", "Staff", "Staff"]:
        make_employee(role=role)
    with django_assert_max_num_queries(12):
        assert client.get("/app/staff/employees/").status_code == 200


@pytest.mark.django_db
def test_shared_demo_accounts_are_read_only_in_demo_mode(
    client_for, make_employee, make_user, settings
):
    """Public demo: the owner can't demote or deactivate the advertised logins (visitor lockout)."""
    settings.DEMO_MODE = True
    demo_cashier = make_employee(role="Cashier", user=make_user("Cashier", username="cashier"))
    visitor_made = make_employee(role="Cashier")
    client = client_for("Owner")
    assert client.get(f"/app/staff/employees/{demo_cashier.pk}/edit/").status_code == 403
    assert client.get(f"/app/staff/employees/{visitor_made.pk}/edit/").status_code == 200
    html = client.get("/app/staff/employees/").content.decode()
    assert f"/app/staff/employees/{demo_cashier.pk}/edit/" not in html


@pytest.mark.django_db
def test_demo_accounts_are_editable_outside_demo_mode(client_for, make_employee, make_user):
    demo_cashier = make_employee(role="Cashier", user=make_user("Cashier", username="cashier"))
    assert (
        client_for("Owner").get(f"/app/staff/employees/{demo_cashier.pk}/edit/").status_code == 200
    )
