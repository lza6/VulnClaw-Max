"""Finding triage metadata persists in target state."""

from __future__ import annotations

import pytest


def _target_with_finding(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    from vulnclaw.agent.context import SessionState
    from vulnclaw.config.domain_models import VulnerabilityFinding

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path)
    session = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(
        title="SQL Injection",
        severity="High",
        vuln_type="SQLi",
        description="Boolean-based SQLi confirmed",
    )
    finding.mark_verified(note="verified")
    session.add_finding(finding)
    store.save_target_state("https://example.com", session, command="scan")
    return "https://example.com"


def test_list_and_triage_finding(monkeypatch, tmp_path):
    import vulnclaw.web.services.finding_service as service

    target = _target_with_finding(monkeypatch, tmp_path)
    findings = service.list_findings(target)
    assert len(findings) == 1
    assert findings[0].title == "SQL Injection"
    assert findings[0].triage_status == "new"

    updated = service.update_finding(
        target,
        findings[0].finding_key,
        triage_status="confirmed",
        note="reproduced on staging",
        assignee="alice",
    )
    assert updated is not None
    assert updated.triage_status == "confirmed"

    reloaded = service.list_findings(target)
    assert reloaded[0].triage_status == "confirmed"
    assert reloaded[0].note == "reproduced on staging"
    assert reloaded[0].assignee == "alice"


def test_unknown_finding_returns_none(monkeypatch, tmp_path):
    import vulnclaw.web.services.finding_service as service

    target = _target_with_finding(monkeypatch, tmp_path)
    assert service.update_finding(target, "missing::key", triage_status="triaged") is None
    assert service.list_findings("https://missing.example") == []


def test_invalid_triage_status_is_rejected(monkeypatch, tmp_path):
    import vulnclaw.web.services.finding_service as service

    target = _target_with_finding(monkeypatch, tmp_path)
    key = service.list_findings(target)[0].finding_key
    with pytest.raises(ValueError):
        service.update_finding(target, key, triage_status="bogus")  # type: ignore[arg-type]
