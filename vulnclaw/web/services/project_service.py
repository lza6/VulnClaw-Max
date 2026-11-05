"""Project workspace model for the Web UI.

A project is a small JSON record under ``PROJECTS_DIR/<slug>/project.json``.
Targets are associated by exact target string; target state itself stays in the
existing ``TARGETS_DIR`` so the executor does not need a second identity model.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from vulnclaw.config.settings import PROJECTS_DIR, ensure_dirs
from vulnclaw.run_context import atomic_write_json
from vulnclaw.web.schemas import ProjectView

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        slug = f"project-{uuid.uuid4().hex[:8]}"
    return slug[:64]


def _project_dir(slug: str) -> Path | None:
    if not _SLUG_RE.fullmatch(slug):
        return None
    return PROJECTS_DIR / slug


def _view(raw: dict) -> ProjectView:
    return ProjectView(
        slug=str(raw.get("slug") or ""),
        name=str(raw.get("name") or ""),
        customer=str(raw.get("customer") or ""),
        scope=str(raw.get("scope") or ""),
        created_at=str(raw.get("created_at") or ""),
        targets=[str(item) for item in raw.get("targets") or [] if item],
    )


def list_projects(limit: int = 100) -> list[ProjectView]:
    if limit < 1:
        raise ValueError("limit must be positive")
    ensure_dirs()
    entries: list[tuple[float, Path]] = []
    for manifest in PROJECTS_DIR.glob("*/project.json"):
        try:
            entries.append((manifest.stat().st_mtime, manifest))
        except OSError:
            continue
    entries.sort(key=lambda item: item[0], reverse=True)

    projects: list[ProjectView] = []
    for _mtime, manifest in entries[:limit]:
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            projects.append(_view(raw))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return projects


def get_project(slug: str) -> ProjectView | None:
    directory = _project_dir(slug)
    if directory is None:
        return None
    manifest = directory / "project.json"
    if not manifest.is_file():
        return None
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _view(raw) if isinstance(raw, dict) else None


def create_project(
    name: str,
    *,
    customer: str = "",
    scope: str = "",
    targets: list[str] | None = None,
) -> ProjectView:
    slug = _slugify(name)
    directory = PROJECTS_DIR / slug
    if (directory / "project.json").exists():
        raise ValueError(f"project already exists: {slug}")

    raw = {
        "slug": slug,
        "name": name.strip(),
        "customer": customer.strip(),
        "scope": scope.strip(),
        "created_at": datetime.now().isoformat(),
        "targets": list(dict.fromkeys(targets or [])),
    }
    atomic_write_json(directory / "project.json", raw)
    (directory / "reports").mkdir(parents=True, exist_ok=True)
    return _view(raw)


def assign_target(slug: str, target: str) -> ProjectView | None:
    directory = _project_dir(slug)
    if directory is None:
        return None
    manifest = directory / "project.json"
    if not manifest.is_file():
        return None
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None

    targets = list(raw.get("targets") or [])
    if target not in targets:
        targets.append(target)
    raw["targets"] = targets
    atomic_write_json(manifest, raw)
    return _view(raw)


def find_project_for_target(target: str) -> str | None:
    for project in list_projects():
        if target in project.targets:
            return project.slug
    return None


def report_dir(slug: str) -> Path | None:
    directory = _project_dir(slug)
    if directory is None or not (directory / "project.json").is_file():
        return None
    reports = directory / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports
