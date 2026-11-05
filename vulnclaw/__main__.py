"""Module entry point so ``python -m vulnclaw`` works.

The Rust ratatui TUI (``tui/``) spawns the Python core via
``python -m vulnclaw``; without this file that invocation fails with
"``No module named vulnclaw.__main__``". Keep this in sync with the
console script entry point (``vulnclaw.cli.main:app`` in pyproject.toml).
"""

from vulnclaw.encoding import configure_stdio_utf8

configure_stdio_utf8()

from vulnclaw.cli.main import app  # noqa: E402

if __name__ == "__main__":
    app()
