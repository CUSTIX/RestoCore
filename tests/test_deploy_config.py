"""Guards for deploy files that no unit test exercises: a wrong edit here only shows up in
production (a sleeping database, a bad deploy, a reset that never runs)."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(name):
    return (ROOT / name).read_text()


def test_render_health_check_does_not_touch_the_database():
    """OPS-01: /healthz/ runs SELECT 1, so polling it all day would keep the free Neon database
    awake and spend its monthly compute hours."""
    assert "healthCheckPath: /livez/" in _read("render.yaml")


def test_render_deploys_only_after_ci_passes():
    """OPS-02: a red commit must not go live (every deploy also reseeds and signs visitors out)."""
    assert "autoDeployTrigger: checksPass" in _read("render.yaml")


def test_access_log_does_not_record_query_strings():
    """SEC-06: guest searches (names, phones) and the self-order token travel in the query."""
    script = _read("bin/start.sh")
    assert "--access-logformat" in script and "%(U)s" in script and "%(q)s" not in script


def test_gunicorn_survives_a_slow_request_without_blocking_every_worker():
    """OPS-04: the assistant can hold a request for a minute; sync workers would stall the site."""
    script = _read("bin/start.sh")
    assert "--worker-class gthread" in script and "--max-requests" in script


def test_start_script_is_valid_shell():
    script = str(ROOT / "bin" / "start.sh")
    result = subprocess.run(["sh", "-n", script], capture_output=True)  # noqa: S603, S607
    assert result.returncode == 0, result.stderr.decode()


def test_the_wipe_only_runs_in_demo_mode():
    """OPS-06: a copied environment file must not flush whatever DATABASE_URL points at."""
    script = _read("bin/start.sh")
    assert 'DEMO_MODE:-false}" = "true"' in script


def test_a_bad_reset_hour_is_reported_not_silently_ignored():
    """OPS-05: with a typo the nightly loop used to die quietly and the reset never happened."""
    script = _read("bin/start.sh")
    assert "Nightly demo reset disabled" in script


def test_assistant_worst_case_fits_inside_the_gunicorn_timeout():
    """OPS-04: the time budget is checked only between model calls, so one more call can follow."""
    import re

    from assistant.llm import GeminiClient
    from assistant.services import TIME_BUDGET

    timeout = int(re.search(r"--timeout (\d+)", _read("bin/start.sh")).group(1))
    call_timeout = GeminiClient.__init__.__defaults__[-1]  # the per-call timeout default
    assert TIME_BUDGET + call_timeout < timeout
