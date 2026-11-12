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


# Transactional like the real start script: TRUNCATE can't run inside the usual per-test
# transaction. serialized_rollback restores migration data (the roles) for later tests.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_seed_demo_reset_wipes_visitor_changes_and_keeps_roles(client):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    User = get_user_model()

    call_command("seed_demo")
    manager = User.objects.get(username="manager")
    manager.set_password("changed-by-a-visitor")
    manager.save()
    User.objects.create_user(username="visitor-made", password="x")

    call_command("seed_demo", "--reset")

    assert set(Group.objects.values_list("name", flat=True)) == set(ALL_ROLES)
    assert not User.objects.filter(username="visitor-made").exists()
    assert client.login(username="manager", password="restocore-demo")
    assert client.get("/app/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("demo_mode,is_admin", [(False, True), (True, False)])
def test_seeded_owner_gets_admin_only_outside_the_public_demo(settings, demo_mode, is_admin):
    from django.contrib.auth import get_user_model

    settings.DEMO_MODE = demo_mode
    call_command("seed_demo")
    owner = get_user_model().objects.get(username="owner")
    assert owner.is_superuser is is_admin and owner.is_staff is is_admin
