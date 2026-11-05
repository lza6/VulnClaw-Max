"""Release version must come from a single source."""

from __future__ import annotations

import json
from pathlib import Path

import tomllib

import vulnclaw
import vulnclaw.web


def test_version_matches_every_executable_location():
    root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
    manifest_line = next(
        line
        for line in (root / "version-manifest.txt").read_text(encoding="utf-8").splitlines()
        if line.startswith("VERSION=")
    )

    assert vulnclaw.__version__ == pyproject["project"]["version"]
    assert vulnclaw.web.__version__ == vulnclaw.__version__
    assert package["version"] == vulnclaw.__version__
    assert manifest_line == f"VERSION={vulnclaw.__version__}"


def test_sarif_driver_does_not_hardcode_a_version():
    root = Path(__file__).resolve().parents[2]
    source = (root / "vulnclaw" / "codescan" / "report.py").read_text(encoding="utf-8")
    assert '"version": __version__' in source
    assert '"version": "0.4.1"' not in source


def test_fastapi_app_reports_package_version():
    from vulnclaw.web.app import create_app

    app = create_app()
    assert app.version == vulnclaw.__version__
