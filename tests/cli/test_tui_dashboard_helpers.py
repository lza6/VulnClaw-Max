"""TUI dashboard/summary/slash helpers."""

from __future__ import annotations

from types import SimpleNamespace

from vulnclaw.cli import tui


def test_dispatch_repl_slash(monkeypatch):
    assert tui.dispatch_repl_slash("/").kind == "message"
    assert tui.dispatch_repl_slash("/config").kind == "command"
    assert tui.dispatch_repl_slash("/config now").kind == "command"

    monkeypatch.setattr(tui, "load_skill_by_name", lambda name: {"name": name, "description": "d"} if name == "sql" else None)
    assert tui.dispatch_repl_slash("/sql do it").kind == "run"
    assert tui.dispatch_repl_slash("/sql").kind == "message"
    assert tui.dispatch_repl_slash("/missing").kind == "message"
    assert "skill" in tui.render_slash_skill_help({"name": "sql", "references": ["a"]})


def test_task_draft_and_summary():
    state = tui.build_state_from_options(target="example.com", only_port="443")
    draft = tui.build_task_draft(state)
    assert draft.command == "run" or draft.command
    assert tui.render_task_summary(draft)
    args = tui.build_command_preview_args(draft)
    assert "example.com" in args
    assert tui._parse_action_csv("a,b") == ["a", "b"]
    assert tui._parse_optional_port("443") == 443
    assert tui._parse_optional_port("") is None
    try:
        tui._parse_optional_port("bad")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert tui._safe_int("3") == 3
    assert tui._safe_int("bad") == 0


def test_target_overview(monkeypatch):
    monkeypatch.setattr(tui, "get_target_state_preview", lambda _target: None)
    monkeypatch.setattr(tui, "list_target_snapshots", lambda _target: [])
    assert tui.build_target_overview("").has_history is False
    assert tui.build_target_overview("example.com").has_history is False

    def boom(_target):
        raise RuntimeError("x")

    monkeypatch.setattr(tui, "get_target_state_preview", boom)
    overview = tui.build_target_overview("example.com")
    assert overview.error

    monkeypatch.setattr(
        tui,
        "get_target_state_preview",
        lambda _target: {
            "target": "example.com",
            "phase": "recon",
            "findings_count": 2,
            "verified_count": 1,
            "pending_count": 1,
            "constraints": {"only_host": "example.com"},
            "constraint_violations": ["x"],
        },
    )
    monkeypatch.setattr(tui, "list_target_snapshots", lambda _target: [1])
    overview = tui.build_target_overview("example.com")
    assert overview.has_history and overview.snapshot_count == 1
    assert overview.violations_count == 1


def test_runtime_diagnostic(monkeypatch):
    config = SimpleNamespace(
        llm=SimpleNamespace(provider="p", model="m", api_key="k")
    )
    monkeypatch.setattr(tui, "_command_version", lambda *_a: "v1")
    monkeypatch.setattr(tui.shutil, "which", lambda _name: "/bin/x")
    import vulnclaw.mcp.diagnostics as diagnostics

    monkeypatch.setattr(
        diagnostics,
        "get_mcp_diagnostics",
        lambda: SimpleNamespace(
            total_services=1,
            running_services=1,
            local_services=1,
            placeholder_services=0,
            tool_count=3,
        ),
    )
    diag = tui.build_runtime_diagnostic(config)
    assert diag.provider == "p" and diag.mcp_tool_count == 3
    assert tui.build_runtime_diagnostic_panel(config) is not None


def test_format_helpers_and_scope_persistence(monkeypatch, tmp_path):
    overview = tui.TuiTargetOverview(
        target="example.com",
        has_history=True,
        snapshot_count=2,
        phase="recon",
        findings_count=3,
        verified_count=1,
        pending_count=2,
        constraints_summary="host example.com",
        violations_count=1,
        last_command="recon",
    )
    assert "2 snapshots" in tui._format_target_history_line(overview)
    assert "3" in tui._format_findings_line(overview)
    assert tui._format_constraints_summary({"only_host": "example.com"})
    assert tui._format_constraints_summary(None)
    assert tui._safe_int(True) in {0, 1}

    state = tui.TuiState(target="example.com", allow_actions=["recon"], block_actions=["exploit"])
    assert tui._effective_allow_actions(state)
    assert tui._effective_block_actions(state) == ("exploit",)
    config = SimpleNamespace()
    tui._persist_scope_state(state, config)
    restored = tui.TuiState()
    tui._restore_scope_state(restored, config)
    assert restored.target in {"example.com", ""}
    assert tui._draft_from_state(state).target == "example.com"
    assert tui._build_task_summary_panel(tui._draft_from_state(state)) is not None
    assert tui._metric_panel("x", "y", "white") is not None
    assert tui._command_version("definitely-not-a-command") == ""
