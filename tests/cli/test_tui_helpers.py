"""Pure/utility helpers from the TUI module."""

from __future__ import annotations

from types import SimpleNamespace

from vulnclaw.cli import tui


def test_find_at_context_and_expand(monkeypatch):
    assert tui.find_at_context("@sql", 4) == ("", "sql")
    assert tui.find_at_context("email@test", 10) is None
    assert tui.find_at_context("no at", 5) is None

    monkeypatch.setattr(tui, "load_skill_by_name", lambda name: {"name": name} if name == "sql" else None)
    assert tui.expand_at_skills("@sql") == "Use VulnClaw skill sql."
    assert tui.expand_at_skills("@nope") == "@nope"
    assert tui.expand_at_skills("plain") == "plain"


def test_build_state_from_options():
    state = tui.build_state_from_options(
        target=" example.com ",
        only_port=443,
        allow_actions="recon,scan",
        block_actions=("exploit",),
        resume=False,
    )
    assert state.target == "example.com"
    assert state.only_port == "443"
    assert state.allow_actions == ["recon", "scan"]
    assert state.block_actions == ["exploit"]
    assert state.resume is False


def test_modes_menus_and_commands():
    modes = tui._build_modes()
    assert set(modes) == {"quick", "standard", "deep", "continuous"}
    assert tui._build_menu_items()
    assert tui._build_slash_commands()
    assert tui._build_repl_commands()
    assert tui._resolve_repl_command("config") == "config"
    assert tui._resolve_repl_command("definitely-missing") == ""


def test_task_draft_command_line():
    draft = tui.TuiTaskDraft(
        command="recon",
        target="example.com",
        only_port=443,
        only_host="example.com",
        allow_actions=("recon",),
        block_actions=("exploit",),
    )
    assert draft.command_line.startswith("vulnclaw recon")
    assert "example.com" in draft.command_line


def test_render_home_and_dashboard(monkeypatch):
    config = SimpleNamespace(
        llm=SimpleNamespace(provider="custom", model="m", api_key="x", api_keys=[]),
        session=SimpleNamespace(language="en", show_thinking=False),
        mcp=SimpleNamespace(servers={}),
    )
    monkeypatch.setattr(tui, "load_config", lambda: config)
    text = tui.render_tui_home(tui.TuiState(target="example.com"), width=80)
    assert "example.com" in text
    dashboard = tui.build_dashboard(config, tui.TuiState())
    assert dashboard is not None


def test_palette_helpers():
    assert tui.skill_display_description({"description": "desc", "short_description": "short"})
    assert isinstance(tui.list_skill_palette_entries(), list)
    assert isinstance(tui.build_at_palette_entries(), list)
    assert isinstance(tui.list_repl_palette_entries(), list)
    assert isinstance(tui.build_slash_palette_entries(), list)
    assert isinstance(tui.slash_completion_style_rules(), dict)


def test_run_tui_once_and_binary(monkeypatch, capsys):
    tui.run_tui(once=True)
    assert "VulnClaw" in capsys.readouterr().out

    monkeypatch.delenv("VULNCLAW_TUI_BINARY", raising=False)
    monkeypatch.setattr(tui.shutil, "which", lambda _name: None)
    monkeypatch.setattr(tui.Path, "exists", lambda _self: False)
    assert tui._find_tui_binary() is None
    monkeypatch.setenv("VULNCLAW_TUI_BINARY", "x")
    assert tui._find_tui_binary() == "x"
    monkeypatch.setattr(tui.subprocess, "call", lambda *_a, **_k: 0)
    try:
        tui.run_tui(initial_state=tui.TuiState())
    except SystemExit as exc:
        assert exc.code == 0


def test_clipboard_read(monkeypatch):
    import base64

    class Completed:
        returncode = 0
        stdout = base64.b64encode("hello".encode())

    monkeypatch.setattr(tui.subprocess, "run", lambda *_a, **_k: Completed())
    assert tui._read_system_clipboard() in {"hello", None}


def test_run_pt_tui_builds_and_runs(monkeypatch):
    import prompt_toolkit

    class FakeApp:
        def __init__(self, **_kwargs):
            pass

        def run(self):
            return None

        def exit(self):
            return None

    monkeypatch.setattr(prompt_toolkit, "Application", FakeApp)
    config = SimpleNamespace(
        llm=SimpleNamespace(provider="p", model="m", api_key="k", api_keys=[]),
        session=SimpleNamespace(language="en", show_thinking=False),
        mcp=SimpleNamespace(servers={}),
    )
    session = {"config": config, "state": tui.TuiState(target="example.com")}
    assert tui._run_pt_tui(session) is None
