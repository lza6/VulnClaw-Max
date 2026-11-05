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
