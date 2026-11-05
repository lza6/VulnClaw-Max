"""TUI/REPL completion helpers."""

from __future__ import annotations

import asyncio

from vulnclaw.cli import tui


class _Doc:
    def __init__(self, text: str, cursor: int | None = None):
        self.text = text
        self.cursor_position = len(text) if cursor is None else cursor
        self.text_before_cursor = text[: self.cursor_position]


async def _collect_async(completer, doc):
    return [item async for item in completer.get_completions_async(doc, None)]


def test_slash_completer_variants():
    completer = tui._build_slash_completer()
    assert asyncio.run(_collect_async(completer, _Doc("plain"))) == []
    assert asyncio.run(_collect_async(completer, _Doc("/")))
    assert asyncio.run(_collect_async(completer, _Doc("/co")))
    assert asyncio.run(_collect_async(completer, _Doc("/.")))


def test_at_completer():
    completer = tui._build_at_completer()
    assert asyncio.run(_collect_async(completer, _Doc("plain"))) == []
    asyncio.run(_collect_async(completer, _Doc("@")))


def test_repl_slash_completer_and_style():
    completer = tui.build_repl_slash_completer()
    assert list(completer.get_completions(_Doc("/"), None))
    assert list(completer.get_completions(_Doc("x"), None)) == []
    assert tui.build_repl_slash_style() is not None
