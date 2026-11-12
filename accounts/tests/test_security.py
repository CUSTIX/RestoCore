import pytest
from django.test import RequestFactory

from accounts import services
from conftest import PASSWORD
from core import throttle
from core.models import ThrottleEvent

LOGIN = "/accounts/login/"


def _try(client, username, password, ip="203.0.113.7"):
    return client.post(LOGIN, {"username": username, "password": password}, REMOTE_ADDR=ip)


@pytest.mark.django_db
def test_wrong_password_is_recorded_and_right_one_clears_it(client, make_user):
    user = make_user("Staff")
    _try(client, user.username, "wrong")
    assert (
        throttle.count("login-user-ip", f"{user.username}|203.0.113.7", services.LOGIN_WINDOW) == 1
    )
    assert _try(client, user.username, PASSWORD).status_code == 302
    assert (
        throttle.count("login-user-ip", f"{user.username}|203.0.113.7", services.LOGIN_WINDOW) == 0
    )


@pytest.mark.django_db
def test_five_failures_lock_that_user_from_that_ip_even_with_the_right_password(client, make_user):
    user = make_user("Staff")
    for _ in range(services.MAX_FAILURES_PER_USER_IP):
        _try(client, user.username, "wrong")
    response = _try(client, user.username, PASSWORD)
    assert response.status_code == 200  # form re-rendered, not logged in
    assert "Too many failed sign-in attempts" in response.content.decode()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_lockout_does_not_block_the_same_user_from_another_ip(client, make_user):
    user = make_user("Staff")
    for _ in range(services.MAX_FAILURES_PER_USER_IP):
        _try(client, user.username, "wrong", ip="203.0.113.7")
    assert _try(client, user.username, PASSWORD, ip="198.51.100.20").status_code == 302


@pytest.mark.django_db
def test_password_spraying_from_one_ip_is_locked(client, make_user):
    user = make_user("Staff")
    for i in range(services.MAX_FAILURES_PER_IP):
        _try(client, f"guess{i}", "wrong")
    assert _try(client, user.username, PASSWORD).status_code == 200


@pytest.mark.django_db
def test_failures_outside_the_window_do_not_count(client, make_user):
    import datetime as dt

    from django.utils import timezone

    user = make_user("Staff")
    for _ in range(services.MAX_FAILURES_PER_USER_IP):
        _try(client, user.username, "wrong")
    ThrottleEvent.objects.update(created_at=timezone.now() - dt.timedelta(minutes=16))
    assert _try(client, user.username, PASSWORD).status_code == 302


def test_client_ip_ignores_forwarded_headers_unless_configured(settings):
    rf = RequestFactory()
    request = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4")
    settings.CLIENT_IP_HEADER = ""
    assert throttle.client_ip(request) == "10.0.0.1"  # forged X-Forwarded-For is ignored

    request = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.5")
    settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    assert throttle.client_ip(request) == "198.51.100.5"


def test_client_ip_rejects_garbage(settings):
    settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    request = RequestFactory().get("/", REMOTE_ADDR="", HTTP_CF_CONNECTING_IP="<script>")
    assert throttle.client_ip(request) is None


@pytest.mark.django_db
def test_password_change_works_normally(client_for):
    assert client_for("Staff").get("/accounts/password/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_password_change_is_disabled_on_the_public_demo(client_for, settings, method):
    settings.DEMO_MODE = True
    client = client_for("Owner")
    response = getattr(client, method)(
        "/accounts/password/",
        {
            "old_password": PASSWORD,
            "new_password1": "N3w-pass-xyz!",
            "new_password2": "N3w-pass-xyz!",
        },
    )
    assert response.status_code == 403
    client.user.refresh_from_db()
    assert client.user.check_password(PASSWORD)


@pytest.mark.django_db
def test_password_change_still_requires_login_in_demo_mode(client, settings):
    settings.DEMO_MODE = True
    response = client.get("/accounts/password/")
    assert response.status_code == 302 and "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_django_admin_login_is_throttled_too(client, django_user_model):
    django_user_model.objects.create_superuser("root", password=PASSWORD)
    for _ in range(services.MAX_FAILURES_PER_USER_IP):
        client.post(
            "/admin/login/", {"username": "root", "password": "wrong"}, REMOTE_ADDR="203.0.113.9"
        )
    response = client.post(
        "/admin/login/?next=/admin/",
        {"username": "root", "password": PASSWORD},
        REMOTE_ADDR="203.0.113.9",
    )
    assert response.status_code == 200
    assert "Too many failed sign-in attempts" in response.content.decode()


@pytest.mark.django_db
def test_failed_logins_without_an_ip_do_not_share_one_lockout(client, make_user, settings):
    """Unknown IPs must not pool into one bucket that a single attacker could fill for everyone."""
    settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"  # header missing below -> REMOTE_ADDR ""
    victim = make_user("Staff")
    for i in range(services.MAX_FAILURES_PER_IP):
        _try(client, f"spray{i}", "wrong", ip="")
    assert _try(client, victim.username, PASSWORD, ip="").status_code == 302
