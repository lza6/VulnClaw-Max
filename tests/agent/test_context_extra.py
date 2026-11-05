"""SessionState bookkeeping helpers."""

from __future__ import annotations

from vulnclaw.agent.context import SessionState


def test_recon_and_facts():
    state = SessionState(target="example.com")
    state.add_recon_subdomain("a.example.com")
    state.add_recon_subdomain("a.example.com")
    assert "a.example.com" in state.recon_data["subdomains"]
    state.mark_recon_dimension("ports")
    assert state.is_recon_complete() is False
    assert isinstance(state.get_recon_status_text(), str)
    state.add_confirmed_fact("the sky is blue")
    state.add_confirmed_fact("the sky is blue")
    state.add_assumption("maybe later")
    assert state.research is not None


def test_constraints_and_steps():
    state = SessionState(target="example.com")
    state.add_constraint_violation("violation")
    state.add_constraint_violation_event(
        source="tool", action="exploit", code="x", severity="high", summary="blocked"
    )
    assert state.constraint_violations
    assert state.constraint_violation_events
    state.add_step("recon", "output", "reason")
    state.add_note("note")
    summary = state.get_step_summary()
    assert summary


def test_save_load(tmp_path):
    state = SessionState(target="example.com")
    path = tmp_path / "session.json"
    state.set_save_path(path)
    state.save()
    loaded = SessionState.load(path)
    assert loaded.target == "example.com"
