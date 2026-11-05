"""Console encoding setup for Windows terminals.

VulnClaw targets Windows as a first-class platform, but the default console
code page is often GBK. Rich's legacy Windows renderer then raises
``UnicodeEncodeError`` for characters such as ``⚠``. Entry points opt into
UTF-8 output so an informational banner can never abort a task.
"""

from __future__ import annotations

import sys


def configure_stdio_utf8() -> None:
    """Force UTF-8 console I/O on Windows, best-effort.

    Only this process's streams are reconfigured. Setting ``PYTHONUTF8`` in
    ``os.environ`` would leak into every child process and can break callers
    that decode child output with the legacy locale code page.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            continue
