"""Constraint audit export must match the aggregated events."""

from __future__ import annotations

import json


def _seed(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.constraint_audit_service as service
    from vulnclaw.agent.context import SessionState

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path)
    monkeypatch.setattr(service, "TARGETS_DIR", tmp_path)
    session = SessionState(target="https://example.com")
    session.add_constraint_violation_event(
        source="tool",
        action="exploit",
        tool_name="fetch",
        code="tool_action_blocked",
        severity="high",
        summary="blocked exploit",
        detail="GET /admin",
    )
    store.save_target_state("https://example.com", session, command="scan")


def test_jsonl_export(monkeypatch, tmp_path):
    import vulnclaw.web.services.constraint_audit_service as service

    _seed(monkeypatch, tmp_path)
    content, media_type = service.export_constraint_audit("jsonl")
    assert media_type == "application/x-ndjson"
    lines = [line for line in content.splitlines() if line]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["code"] == "tool_action_blocked"
    assert event["target"] == "https://example.com"


def test_csv_export(monkeypatch, tmp_path):
    import vulnclaw.web.services.constraint_audit_service as service

    _seed(monkeypatch, tmp_path)
    content, media_type = service.export_constraint_audit("csv")
    assert media_type == "text/csv"
    lines = content.splitlines()
    assert lines[0].startswith("target,timestamp,code,")
    assert "tool_action_blocked" in lines[1]


def test_unknown_format_is_rejected(monkeypatch, tmp_path):
    import pytest

    import vulnclaw.web.services.constraint_audit_service as service

    _seed(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        service.export_constraint_audit("xml")
