"""Release version must come from a single source."""

from __future__ import annotations

import json
from pathlib import Path

try:  # tomllib 是 3.11 才进标准库，项目声明支持 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 仅在 3.10 上走到
    import tomli as tomllib

import vulnclaw
import vulnclaw.web


def test_version_matches_every_executable_location():
    root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert vulnclaw.__version__ == pyproject["project"]["version"]
    assert vulnclaw.web.__version__ == vulnclaw.__version__
    assert package["version"] == vulnclaw.__version__
    assert not (root / "version-manifest.txt").exists()


def test_sarif_driver_does_not_hardcode_a_version():
    root = Path(__file__).resolve().parents[2]
    source = (root / "vulnclaw" / "codescan" / "report.py").read_text(encoding="utf-8")
    assert '"version": __version__' in source
    assert '"version": "0.4.1"' not in source


def test_fastapi_app_reports_package_version():
    from vulnclaw.web.app import create_app

    app = create_app()
    assert app.version == vulnclaw.__version__
