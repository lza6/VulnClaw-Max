"""TUI config editors and prompt helpers (prompt-chain fallback path)."""

from __future__ import annotations

from pathlib import Path

import pytest

import vulnclaw.cli.tui as tui
from vulnclaw.config.schema import VulnClawConfig


class _Screen:
    """Console double: blank input keeps every prompt at its default."""

    def __init__(self):
        self.lines: list[str] = []

    def print(self, *args, **_kwargs):
        self.lines.append(" ".join(str(arg) for arg in args))

    def input(self, _prompt="", *, password=False, stream=None):
        return ""


@pytest.fixture
def screen():
    return _Screen()


@pytest.fixture
def echo_prompts(monkeypatch):
    """Echo the current value back for every prompt type."""
    monkeypatch.setattr(tui, "_prompt_text_value", lambda s, label, current: current)
    monkeypatch.setattr(
        tui, "_prompt_choice_value", lambda s, label, choices, current: current if current in choices else choices[0]
    )
    monkeypatch.setattr(tui, "_prompt_bool_value", lambda s, label, current: current)
    monkeypatch.setattr(tui, "_prompt_int_value", lambda s, label, current: current)
    monkeypatch.setattr(tui, "_prompt_float_value", lambda s, label, current: current)


# ── Prompt helpers ───────────────────────────────────────────────────


def test_prompt_text_value_keeps_current_on_blank(monkeypatch):
    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "")
    assert tui._prompt_text_value(_Screen(), "Label", "keep") == "keep"

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "!clear")
    assert tui._prompt_text_value(_Screen(), "Label", "keep") == ""

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "new")
    assert tui._prompt_text_value(_Screen(), "Label", "keep") == "new"


def test_prompt_choice_value_defaults_into_the_choices(monkeypatch):
    seen: dict = {}

    def ask(screen, label, *, default="", choices=None):
        seen["default"] = default
        return default

    monkeypatch.setattr(tui, "_config_prompt_ask", ask)

    assert tui._prompt_choice_value(_Screen(), "Mode", ["a", "b"], "b") == "b"
    assert seen["default"] == "b"
    assert tui._prompt_choice_value(_Screen(), "Mode", ["a", "b"], "zzz") == "a"


def test_prompt_int_and_float_reprompt_on_bad_input(monkeypatch):
    answers = iter(["nope", "12"])
    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: next(answers))
    assert tui._prompt_int_value(_Screen(), "Count", 3) == 12

    answers = iter(["nope", "0.75"])
    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: next(answers))
    assert tui._prompt_float_value(_Screen(), "Ratio", 0.5) == 0.75

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "")
    assert tui._prompt_int_value(_Screen(), "Count", 3) == 3
    assert tui._prompt_float_value(_Screen(), "Ratio", 0.5) == 0.5


def test_prompt_env_value_parses_pairs_and_supports_clear(monkeypatch):
    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "A=1, B = two")
    assert tui._prompt_env_value(_Screen(), "Env", {"OLD": "x"}) == {"A": "1", "B": "two"}

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "!clear")
    assert tui._prompt_env_value(_Screen(), "Env", {"OLD": "x"}) == {}

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "")
    assert tui._prompt_env_value(_Screen(), "Env", {"OLD": "x"}) == {"OLD": "x"}

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "NOEQUALS")
    with pytest.raises(ValueError, match="KEY=value"):
        tui._prompt_env_value(_Screen(), "Env", None)

    monkeypatch.setattr(tui, "_config_prompt_ask", lambda *a, **k: "=value")
    with pytest.raises(ValueError, match="cannot be blank"):
        tui._prompt_env_value(_Screen(), "Env", None)


def test_read_config_prompt_raw_raises_on_escape(monkeypatch):
    class _Prompt:
        ask = staticmethod(lambda *a, **k: "\x1b")

    monkeypatch.setattr(tui, "Prompt", _Prompt)
    monkeypatch.setattr(tui.sys.stdin, "isatty", lambda: False, raising=False)

    with pytest.raises(tui._ConfigTuiExit):
        tui._read_config_prompt_raw("Label")

    _Prompt.ask = staticmethod(lambda *a, **k: "  value  ")
    assert tui._read_config_prompt_raw("Label") == "value"


def test_config_prompt_ask_retries_until_valid(monkeypatch):
    answers = iter(["maybe", "a"])
    monkeypatch.setattr(tui, "_read_config_prompt_raw", lambda *a, **k: next(answers))

    assert tui._config_prompt_ask(_Screen(), "Pick", choices=["a", "b"]) == "a"
    assert any("maybe" in line for line in _Screen().lines) is False


# ── Section editors ──────────────────────────────────────────────────


def test_edit_session_config_echoes_every_field(screen, echo_prompts):
    config = VulnClawConfig()
    before = config.model_dump()

    updated = tui._edit_session_config(screen, config)

    assert updated.session.output_dir == Path(before["session"]["output_dir"])
    assert screen.lines, "the editor must report which section it opened"


def test_edit_safety_config_echoes_every_field(screen, echo_prompts):
    config = VulnClawConfig()

    updated = tui._edit_safety_config(screen, config)

    assert updated.safety == config.safety
    assert screen.lines


def test_edit_recon_config_echoes_every_field(screen, echo_prompts):
    config = VulnClawConfig()

    updated = tui._edit_recon_config(screen, config)

    assert updated.recon == config.recon


def test_edit_llm_config_echoes_every_field(screen, echo_prompts, monkeypatch):
    config = VulnClawConfig()
    monkeypatch.setattr(tui, "_prompt_secret_text_value", lambda s, label, current: current)
    monkeypatch.setattr(tui, "_prompt_env_value", lambda s, label, current: current or {})

    updated = tui._edit_llm_config(screen, config)

    assert updated.llm.provider == config.llm.provider
    assert updated.llm.model == config.llm.model


def test_edit_mcp_config_can_toggle_and_delete_servers(screen, echo_prompts, monkeypatch):
    config = VulnClawConfig()
    config.mcp.servers["demo"] = tui.MCPServerConfig(
        name="demo", transport={"type": "stdio", "command": "noop"}
    )
    monkeypatch.setattr(tui, "_prompt_mcp_server", lambda screen, name, server: server)

    updated = tui._edit_mcp_config(screen, config)

    assert "demo" in updated.mcp.servers
