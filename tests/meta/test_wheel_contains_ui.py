"""Release artifacts must contain the built Web UI."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.verify_dist_artifacts import verify_dist_artifacts


def _artifacts(root: Path, *, include_ui: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    wheel = root / "vulnclaw-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        if include_ui:
            archive.writestr("vulnclaw/web/dist/index.html", "<html></html>")
    (root / "vulnclaw-0.0.0.tar.gz").write_bytes(b"not-empty")


def test_wheel_contains_ui(tmp_path):
    _artifacts(tmp_path, include_ui=True)
    assert verify_dist_artifacts(tmp_path, version="0.0.0")


def test_wheel_without_ui_is_rejected(tmp_path):
    _artifacts(tmp_path, include_ui=False)
    with pytest.raises(ValueError, match="built Web UI"):
        verify_dist_artifacts(tmp_path, version="0.0.0")
