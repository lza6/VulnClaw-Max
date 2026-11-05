"""TUI dashboard + config panel internals driven through their real wiring.

`_run_pt_tui` and `_run_config_panel` build prompt_toolkit closures and hand them
to an ``Application``. The fake application keeps the layout and key bindings so
the tests can invoke exactly the closures the user's keystrokes would hit.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest

import vulnclaw.cli.tui as tui


class _ImmediateLoop:
    """Loop double: thread-safe scheduling runs inline."""

    def call_soon_threadsafe(self, callback: Callable[[], None]) -> None:
        callback()


class _FakeApp:
    last: "_FakeApp | None" = None

    def __init__(self, *, layout=None, key_bindings=None, **_kwargs) -> None:
        _FakeApp.last = self
        self.layout = layout
        self.key_bindings = key_bindings
        self.exited = False
        self.invalidated = 0
        self.loop = _ImmediateLoop()

    def run(self) -> None:
        return None

    def exit(self) -> None:
        self.exited = True

    def invalidate(self) -> None:
        self.invalidated += 1


class _FakeEvent:
    def __init__(self, *, data: str = "", app: Any = None) -> None:
        self.data = data
        self.app = app


@pytest.fixture
def fake_app(monkeypatch):
    import prompt_toolkit

    _FakeApp.last = None
    monkeypatch.setattr(prompt_toolkit, "Application", _FakeApp)
    return _FakeApp


def _handlers(key_bindings: Any) -> dict[str, Callable]:
    """Map key name → handler, keeping the first (app-owned) binding."""
    table: dict[str, Callable] = {}
    for binding in key_bindings.bindings:
        keys = binding.keys
        if not keys:
            continue
        name = getattr(keys[0], "value", keys[0])
        table.setdefault(str(name), binding.handler)
    return table


def _windows(layout: Any) -> list[Any]:
    container = layout.container
    if hasattr(container, "content") and hasattr(container.content, "children"):
        container = container.content
    return list(getattr(container, "children", []))


def _controls(layout: Any) -> list[Any]:
    return [window.content for window in _windows(layout) if hasattr(window, "content")]


def _session() -> dict[str, Any]:
    config = SimpleNamespace(
        llm=SimpleNamespace(provider="p", model="m", api_key="k", api_keys=[]),
        session=SimpleNamespace(language="en", show_thinking=False),
        mcp=SimpleNamespace(servers={}),
    )
    return {"config": config, "state": tui.TuiState(target="example.com")}


# ── Dashboard cycle ──────────────────────────────────────────────────


def test_pt_tui_renders_status_bar_for_every_prompt_kind(fake_app):
    session = _session()

    assert tui._run_pt_tui(session) is None
    app = fake_app.last
    windows = _windows(app.layout)
    dashboard = windows[0].content
    status = windows[2].content
    assert "example.com" in str(dashboard.text())

    session["_prompt"] = ("input", "Ask something", "cb", "")
    assert "Ask something" in str(status.text())
    session["_prompt"] = ("choice", "Pick", ["a", "b"], "cb")
    assert "Pick" in str(status.text())
    session["_prompt"] = ("confirm", "Sure?", "cb")
    assert "Sure?" in str(status.text())
    session["_prompt"] = ("message", "Heads up", None)
    assert "Heads up" in str(status.text())
    session["_prompt"] = ("chain", [("only_host", "Host", "")], 0, "cb")
    assert "[1/1] Host" in str(status.text())

    session["_prompt"] = None
    session["_message"] = "saved"
    assert "saved" in str(status.text())
    session["_message"] = ""
    assert status.text() == []


def test_pt_tui_palette_tracks_slash_flag_and_at_contexts(fake_app):
    session = _session()
    tui._run_pt_tui(session)
    app = fake_app.last
    windows = _windows(app.layout)
    buffer = windows[3].content.buffer
    palette = app.layout.container.floats[0].content.content

    buffer.text = "/h"
    buffer.cursor_position = len(buffer.text)
    slash_items = palette.text()
    assert slash_items, "a /prefix must open the palette"
    assert any(line[1].startswith("▸") or "▸" in line[1] for line in slash_items)

    buffer.text = "/.sql"
    buffer.cursor_position = len(buffer.text)
    palette.text()

    buffer.text = "ping @re"
    buffer.cursor_position = len(buffer.text)
    palette.text()

    buffer.text = "/h now"
    buffer.cursor_position = len(buffer.text)
    assert palette.text() == []


def test_pt_tui_input_handler_covers_prompt_slash_and_natural_language(fake_app):
    session = _session()
    tui._run_pt_tui(session)
    app = fake_app.last
    buffer = _windows(app.layout)[3].content.buffer

    # Natural language → the session asks for a launch cycle.
    buffer.text = "scan example.com please"
    buffer.accept_handler(buffer)
    assert session["_action"] == "launch"
    assert session["_nl_text"] == "scan example.com please"
    assert session["_nl_history"] == "scan example.com please"
    assert buffer.text == ""

    # Unknown slash command → message, no exit.
    session["_action"] = None
    buffer.text = "/definitely-not-a-command"
    buffer.accept_handler(buffer)
    assert "Unknown command" in session["_message"]

    # A prompt swallows the input instead of treating it as a new task.
    answered: list[str] = []
    session["_prompt"] = ("input", "Name", answered.append, "default")
    buffer.text = ""
    buffer.accept_handler(buffer)
    assert answered == ["default"]
    assert session["_prompt"] is None

    # Message prompts just clear.
    session["_prompt"] = ("message", "ack", None)
    buffer.text = "ok"
    buffer.accept_handler(buffer)
    assert session["_prompt"] is None


def test_pt_tui_key_bindings_navigate_the_palette_and_exit(fake_app):
    session = _session()
    tui._run_pt_tui(session)
    app = fake_app.last
    keys = _handlers(app.key_bindings)
    buffer = _windows(app.layout)[3].content.buffer
    buffer.text = "/h"
    buffer.cursor_position = len(buffer.text)

    keys["down"](_FakeEvent(app=app))
    assert session["_palette_idx"] == 1
    keys["up"](_FakeEvent(app=app))
    keys["up"](_FakeEvent(app=app))
    assert session["_palette_idx"] == 0
    keys["c-i"](_FakeEvent(app=app))
    assert buffer.text.startswith("/")

    # Escape with an active prompt cancels it; without one it quits.
    session["_prompt"] = ("message", "ack", None)
    keys["escape"](_FakeEvent(app=app))
    assert session["_prompt"] is None
    assert session["_action"] != "quit"

    keys["escape"](_FakeEvent(app=app))
    assert session["_action"] == "quit"

    session["_action"] = None
    keys["c-c"](_FakeEvent(app=app))
    assert session["_action"] == "quit"


# ── Config panel ─────────────────────────────────────────────────────


@pytest.fixture
def config_panel(monkeypatch, fake_app):
    from vulnclaw.config.schema import VulnClawConfig

    saved: list[Any] = []
    monkeypatch.setattr(tui, "load_config", lambda: VulnClawConfig())
    monkeypatch.setattr(tui, "save_config", lambda config: saved.append(config))
    return saved


def test_config_panel_renders_the_body_and_saves(config_panel, fake_app):
    tui._run_config_panel()

    app = fake_app.last
    body = app.layout.container.children[0].content
    rendered = str(body.text())
    assert "VulnClaw" in rendered

    keys = _handlers(app.key_bindings)
    for key in ("up", "down", "c-i", "s-tab", "left", "right", "pageup", "pagedown"):
        keys[key](_FakeEvent(app=app))

    # Ctrl-S without an edit has nothing to persist: the panel must stay a no-op
    # rather than write an unchanged config.
    keys["c-s"](_FakeEvent(app=app))
    assert config_panel == []


def test_config_panel_escape_discards(config_panel, fake_app):
    tui._run_config_panel()
    app = fake_app.last
    keys = _handlers(app.key_bindings)

    keys["escape"](_FakeEvent(app=app))
    assert app.exited is True
    assert config_panel == []

    app2 = fake_app.last
    keys2 = _handlers(app2.key_bindings)
    keys2["c-c"](_FakeEvent(app=app2))
    assert app2.exited is True


def test_config_panel_fetch_requires_credentials(config_panel, fake_app):
    tui._run_config_panel()
    app = fake_app.last
    keys = _handlers(app.key_bindings)

    # No API key configured → the fetch action reports why it is idle.
    keys["c-r"](_FakeEvent(app=app))
    keys["c-m"](_FakeEvent(app=app))
    keys[" "](_FakeEvent(app=app))
    keys["c-h"](_FakeEvent(app=app))
    keys["c-v"](_FakeEvent(app=app))
    keys["<any>"](_FakeEvent(app=app, data="x"))


# ── Prompt-chain config editor ───────────────────────────────────────


def test_config_wizard_saves_then_exits(monkeypatch):
    from vulnclaw.config.schema import VulnClawConfig

    choices = iter(["llm", "session", "quit"])
    saved: list[Any] = []
    monkeypatch.setattr(tui, "load_config", lambda: VulnClawConfig())
    monkeypatch.setattr(tui, "save_config", lambda config: saved.append(config))
    monkeypatch.setattr(tui, "_render_config_summary", lambda screen, config: None)
    monkeypatch.setattr(tui, "_prompt_choice_value", lambda screen, label, options, default: next(choices))
    monkeypatch.setattr(
        tui, "_edit_llm_config", lambda screen, config: config
    )
    monkeypatch.setattr(
        tui, "_edit_session_config", lambda screen, config: config
    )

    tui._run_config_wizard()

    assert saved == [], "a quit must discard changes"


def test_config_wizard_quit_path_prints_discard(monkeypatch):
    from vulnclaw.config.schema import VulnClawConfig

    printed: list[Any] = []

    class _Screen:
        def print(self, *args, **_kwargs):
            printed.append(args)

    monkeypatch.setattr(tui, "load_config", lambda: VulnClawConfig())
    monkeypatch.setattr(tui, "Console", lambda *a, **k: _Screen())
    monkeypatch.setattr(tui, "_render_config_summary", lambda screen, config: None)
    monkeypatch.setattr(tui, "_prompt_choice_value", lambda *a, **k: "save")
    monkeypatch.setattr(tui, "save_config", lambda config: None)

    tui._run_config_wizard()

    renderables = [str(getattr(item[0], "renderable", item[0])) for item in printed if item]
    assert any("Config saved." in text for text in renderables)
