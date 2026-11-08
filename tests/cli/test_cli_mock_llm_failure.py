"""CLI exit codes against a real HTTP LLM provider mock (no paid calls).

``tests/cli/test_cli_failure_exit_code.py`` proves the handler converts a typed
LLM failure into exit 1; this module proves the whole process does the same
when a provider actually rejects the credentials.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.mock_llm_server import start_mock_llm_server

ROOT = Path(__file__).resolve().parents[2]
MOCK_SECRET = "sk-mock-secret-123456"


@pytest.fixture
def mock_llm():
    server = start_mock_llm_server()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _run_cli(mock_llm, tmp_path, *argv: str) -> subprocess.CompletedProcess[bytes]:
    (tmp_path / "config.yaml").write_text(
        "llm:\n"
        "  provider: custom\n"
        "  api_key: sk-test\n"
        f"  base_url: {mock_llm.base_url}\n"
        "  model: mock-401\n",
        encoding="utf-8",
    )
    env = dict(
        os.environ,
        VULNCLAW_CONFIG_DIR=str(tmp_path),
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.run(
        [sys.executable, "-m", "vulnclaw", *argv],
        cwd=ROOT,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        env=env,
        timeout=90,
    )


@pytest.mark.parametrize(
    "argv",
    [
        ("recon", "127.0.0.1:1"),
        ("scan", "127.0.0.1:1"),
        ("exploit", "127.0.0.1:1"),
        # solve regressed once by exiting 0 on fatal errors; keep it covered.
        ("run", "127.0.0.1:1", "--engine", "solve"),
    ],
)
def test_command_exits_1_on_rejected_credentials(mock_llm, tmp_path, argv):
    proc = _run_cli(mock_llm, tmp_path, *argv)
    output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")

    assert proc.returncode == 1
    assert "401" in output
    assert MOCK_SECRET not in output
