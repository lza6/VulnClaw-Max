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


def _index_path() -> Path:
    return PROJECTS_DIR / "index.json"


def _load_index() -> dict[str, str]:
    path = _index_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(target): str(slug)
        for target, slug in raw.items()
        if isinstance(target, str) and isinstance(slug, str) and _SLUG_RE.fullmatch(slug)
    }


def _save_index(index: dict[str, str]) -> None:
    atomic_write_json(_index_path(), index)


def _project_manifest(slug: str) -> tuple[Path, dict] | None:
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
    return (manifest, raw) if isinstance(raw, dict) else None


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
    for target in raw["targets"]:
        assign_target(slug, target)
    return get_project(slug) or _view(raw)


def assign_target(slug: str, target: str) -> ProjectView | None:
    """Assign a target to a project, enforcing single-project ownership.

    A target that already belongs to another project is moved: the old project
    loses it and the new project gains it. This keeps report routing
    deterministic.
    """
    loaded = _project_manifest(slug)
    if loaded is None:
        return None
    manifest, raw = loaded

    index = _load_index()
    previous = index.get(target)
    if previous and previous != slug:
        previous_loaded = _project_manifest(previous)
        if previous_loaded is not None:
            previous_manifest, previous_raw = previous_loaded
            previous_targets = [
                item for item in previous_raw.get("targets") or [] if item != target
            ]
            previous_raw["targets"] = previous_targets
            atomic_write_json(previous_manifest, previous_raw)

    targets = list(raw.get("targets") or [])
    if target not in targets:
        targets.append(target)
    raw["targets"] = targets
    atomic_write_json(manifest, raw)
    index[target] = slug
    _save_index(index)
    return _view(raw)


def unassign_target(target: str) -> bool:
    """Remove a target from whichever project owns it."""
    index = _load_index()
    slug = index.pop(target, None)
    if slug is None:
        return False
    loaded = _project_manifest(slug)
    if loaded is not None:
        manifest, raw = loaded
        raw["targets"] = [item for item in raw.get("targets") or [] if item != target]
        atomic_write_json(manifest, raw)
    _save_index(index)
    return True


def find_project_for_target(target: str) -> str | None:
    index = _load_index()
    slug = index.get(target)
    if slug and _project_manifest(slug) is not None:
        return slug
    # Migration fallback for projects created before the single-owner index.
    for project in list_projects():
        if target in project.targets:
            index[target] = project.slug
            _save_index(index)
            return project.slug
    return None


def targets_for_project(slug: str) -> set[str]:
    """Targets owned by ``slug`` according to the single-owner index."""
    return {target for target, owner in _load_index().items() if owner == slug}


def owned_targets() -> set[str]:
    """Every target that belongs to some project."""
    return set(_load_index())


def report_dir(slug: str) -> Path | None:
    directory = _project_dir(slug)
    if directory is None or not (directory / "project.json").is_file():
        return None
    reports = directory / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports
