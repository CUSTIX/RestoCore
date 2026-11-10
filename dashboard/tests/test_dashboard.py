import pytest
from django.core.management import CommandError, call_command

from core.roles import ALL_ROLES


@pytest.mark.django_db
@pytest.mark.parametrize("role", ALL_ROLES)
def test_dashboard_renders_for_every_role(client_for, role):
    assert client_for(role).get("/app/").status_code == 200


@pytest.mark.django_db
def test_dashboard_hides_sales_from_kitchen(client_for):
    html = client_for("Kitchen").get("/app/").content.decode()
    assert "Sales today" not in html and "Low stock" in html


@pytest.mark.django_db
def test_sidebar_shows_only_allowed_sections(client_for):
    html = client_for("Cashier").get("/app/").content.decode()
    assert "Point of sale" in html
    assert "Payroll" not in html and "Employees" not in html


@pytest.mark.django_db
def test_seed_demo_creates_data_and_refuses_to_run_twice(client):
    call_command("seed_demo")
    assert client.login(username="manager", password="restocore-demo")
    assert client.get("/app/").status_code == 200
    with pytest.raises(CommandError):
        call_command("seed_demo")
