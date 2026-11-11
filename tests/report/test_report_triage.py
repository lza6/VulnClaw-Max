"""Report rendering carries triage metadata and token/cost usage."""

from __future__ import annotations

from types import SimpleNamespace

from vulnclaw.agent.context import SessionState
from vulnclaw.config.domain_models import VulnerabilityFinding


def _session() -> SessionState:
    session = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(
        title="SQL Injection",
        severity="High",
        vuln_type="SQLi",
        description="Confirmed SQL injection",
        evidence="id=1' OR '1'='1",
    )
    finding.mark_verified(note="verified")
    session.add_finding(finding)
    return session


def test_report_includes_triage_status_and_assignee(tmp_path):
    from vulnclaw.i18n import init_i18n
    from vulnclaw.report.generator import generate_report

    session = _session()
    finding = session.findings[0]
    context = {
        "finding_meta": {
            finding.finding_id: {
                "triage_status": "confirmed",
                "assignee": "alice",
                "note": "reproduced",
            }
        },
        "runtime_meta": {"tokens_input": 100, "tokens_output": 50, "tokens_total": 150},
    }
    init_i18n(lang="zh")
    try:
        output = generate_report(
            session,
            str(tmp_path / "report.md"),
            target_state_context=context,
        )
    finally:
        init_i18n()
    content = output.read_text(encoding="utf-8")
    assert "处置状态" in content
    assert "confirmed" in content
    assert "alice" in content


def test_report_includes_token_and_cost_usage(tmp_path, monkeypatch):
    import vulnclaw.config.settings as settings
    from vulnclaw.i18n import init_i18n
    from vulnclaw.report.generator import generate_report

    fake_llm = SimpleNamespace(
        input_cost_per_million=2.0,
        output_cost_per_million=4.0,
        cost_currency="USD",
    )
    monkeypatch.setattr(settings, "load_config", lambda: SimpleNamespace(llm=fake_llm))

    session = _session()
    context = {"runtime_meta": {"tokens_input": 1_000_000, "tokens_output": 500_000, "tokens_total": 1_500_000}}
    init_i18n(lang="zh")
    try:
        output = generate_report(
            session,
            str(tmp_path / "report.md"),
            target_state_context=context,
        )
    finally:
        init_i18n()
    content = output.read_text(encoding="utf-8")
    assert "1,500,000" in content or "1500000" in content
    assert "4.0" in content
    assert "USD" in content
