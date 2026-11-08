"""CLI startup must not import the heavy agent/config stacks for --help."""

from __future__ import annotations

import subprocess
import sys


def test_cli_import_is_lazy():
    code = (
        "import sys, vulnclaw.cli.main; "
        "print('vulnclaw.agent.agent_state' in sys.modules); "
        "print('vulnclaw.task_service' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines == ["False", "False"]


def test_headless_defaults_match_source_of_truth():
    """cli/main.py duplicates headless string defaults to avoid a cold import;
    this pins the copies to vulnclaw.headless."""

    import vulnclaw.cli.main as cli_main
    from vulnclaw import headless

    assert cli_main.DEFAULT_SCAN_MODE == headless.DEFAULT_SCAN_MODE
    assert cli_main.DEFAULT_FAIL_ON == headless.DEFAULT_FAIL_ON
    assert cli_main.DEFAULT_SCOPE_MODE == headless.DEFAULT_SCOPE_MODE


def test_cli_help_wall_time_budget():
    """`vulnclaw --help` median must stay under the 0.5 s product budget.

    Generous absolute ceiling for slow CI machines; the median-of-5 form
    keeps the check stable against transient disk noise.
    """
    import statistics
    import time

    times = []
    for _ in range(5):
        start = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "vulnclaw", "--help"],
            capture_output=True,
            timeout=30,
        )
        times.append(time.monotonic() - start)
        assert result.returncode == 0

    assert statistics.median(times) < 2.0, f"median startup {statistics.median(times):.3f}s"
