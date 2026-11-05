"""Compatibility helpers in vulnclaw.cli.__init__."""

from __future__ import annotations

import io
from types import SimpleNamespace

from rich.console import Console

from vulnclaw.cli import (
    TerminalStreamSink,
    _append_action_constraints,
    _append_cli_constraints,
    _append_cli_constraints_compat,
    _collapse_terminal_text,
    _extract_evidence_id,
    _make_solve_event_printer,
    _print_agent_output,
    _print_banner,
    _print_styled_plain,
)


def test_text_helpers():
    text, collapsed = _collapse_terminal_text("x" * 3000)
    assert collapsed and len(text) < 3000
    assert _collapse_terminal_text("short") == ("short", False)
    assert _extract_evidence_id("see [evidence:e12]") == "e12"
    assert _extract_evidence_id("none") == ""
    console = Console(file=io.StringIO())
    _print_styled_plain(console, "prefix", "[b]body[/b]")


def test_terminal_stream_sink():
    console = Console(file=io.StringIO())
    sink = TerminalStreamSink(console, show_thinking=True)
    sink.on_status("Thinking...")
    sink.on_thinking_token("think")
    sink.on_content_token("text")
    sink.on_tool_call("fetch", "args")
    sink.on_tool_result("result " * 1000 + "[evidence:e1]")
    sink.on_stream_end()
    assert "Thinking" in console.file.getvalue()


def test_banner_and_printer():
    console = Console(file=io.StringIO())
    _print_banner()
    printer = _make_solve_event_printer(console)
    for event, payload in (
        ("agent_step", {"step": 1}),
        ("tool_call", {"tool": "fetch", "args": "x"}),
        ("tool_result", {"tool": "fetch", "result": "ok"}),
        ("error", {"error": "bad"}),
        ("unknown", {}),
    ):
        printer(event, payload)


def test_agent_output_and_constraints():
    _print_agent_output("hello", SimpleNamespace(session=SimpleNamespace(show_thinking=False)))
    assert _append_cli_constraints("p", 80, "a.com", "/", "b.com", "/x").startswith("p")
    assert _append_cli_constraints_compat("p", 80, "a.com", "/", "b.com", "/x")
    assert _append_action_constraints("p", "recon,scan", "exploit")
