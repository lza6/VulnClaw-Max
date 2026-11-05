"""Seed one target with a verified finding for E2E flows."""

from __future__ import annotations

import sys

from vulnclaw.agent.context import SessionState
from vulnclaw.config.domain_models import VulnerabilityFinding
from vulnclaw.target_state.store import save_target_state


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    session = SessionState(target=target)
    finding = VulnerabilityFinding(
        title="SQL Injection",
        severity="High",
        vuln_type="SQLi",
        description="Boolean-based SQL injection confirmed during E2E seed.",
        evidence=f"{target}/item?id=1' AND 1=1--",
    )
    finding.mark_verified(note="E2E seed")
    session.add_finding(finding)
    save_target_state(target, session, command="scan")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
