"""Report service for the Web UI backend."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from vulnclaw.config.settings import PROJECTS_DIR, SESSIONS_DIR, ensure_dirs, load_config
from vulnclaw.i18n import init_i18n
from vulnclaw.report.generator import generate_report_from_target_state
from vulnclaw.report.variants import normalize_template
from vulnclaw.target_state.store import load_target_state
from vulnclaw.web.schemas import ReportContentView
from vulnclaw.web.services.project_service import find_project_for_target, report_dir


def _report_item(path: Path, kind: str) -> dict[str, str | int]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "kind": kind,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size_bytes": stat.st_size,
    }


def _report_roots() -> list[Path]:
    roots = [SESSIONS_DIR]
    if PROJECTS_DIR.is_dir():
        roots.extend(
            path for path in PROJECTS_DIR.glob("*/reports") if path.is_dir()
        )
    return roots


def _default_report_path(
    target: str, report_format: str, root: Path = SESSIONS_DIR, template: str = "pentest"
) -> Path:
    safe_target = re.sub(r"[^A-Za-z0-9_.-]+", "_", target or "unknown").strip("._")
    safe_target = safe_target[:80] or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ".html" if report_format == "html" else ".md"
    template_tag = "" if template == "pentest" else f"_{template}"
    return root / f"report_{timestamp}{template_tag}_{safe_target}{suffix}"


def list_reports(limit: int = 50) -> list[dict[str, str | int]]:
    """List recent reports from the sessions directory."""
    ensure_dirs()
    items: list[dict[str, str | int]] = []
    for root in _report_roots():
        prefix = "" if root == SESSIONS_DIR else f"{root.parent.name}/"
        for path in root.glob("*.md"):
            item = _report_item(path, "markdown")
            item["name"] = prefix + path.name
            items.append(item)
        for path in root.glob("*.html"):
            item = _report_item(path, "html")
            item["name"] = prefix + path.name
            items.append(item)
        for path in root.glob("*.pdf"):
            item = _report_item(path, "pdf")
            item["name"] = prefix + path.name
            items.append(item)
        for findings_dir in root.glob("*_findings"):
            if not findings_dir.is_dir():
                continue
            for path in findings_dir.glob("*.json"):
                item = _report_item(path, "json")
                item["name"] = f"{prefix}{findings_dir.name}/{path.name}"
                items.append(item)
            for path in findings_dir.glob("*.sarif"):
                item = _report_item(path, "sarif")
                item["name"] = f"{prefix}{findings_dir.name}/{path.name}"
                items.append(item)
    items.sort(key=lambda item: str(item["modified_at"]), reverse=True)
    return items[:limit]


def generate_target_report(
    target: str,
    output_path: str | None = None,
    report_format: str = "markdown",
    template: str = "pentest",
) -> str:
    """Generate a report from target state and return the saved path."""
    template_kind = normalize_template(template)
    project_slug = find_project_for_target(target)
    root = report_dir(project_slug) if project_slug else SESSIONS_DIR
    if root is None:
        root = SESSIONS_DIR
    root.mkdir(parents=True, exist_ok=True)
    # The report generator picks Chinese vs English from current_lang(). Unlike
    # the scan task path, this standalone endpoint has no ambient i18n state, so
    # initialize it from the saved config.session.language before generating —
    # otherwise the report always falls back to auto-detection (defaults to zh).
    init_i18n(config=load_config())
    raw = load_target_state(target)
    if not raw:
        raise FileNotFoundError(f"Target state not found: {target}")
    requested = report_format.lower()
    normalized_format = "html" if requested == "html" else "markdown"
    path = generate_report_from_target_state(
        raw,
        report_format=normalized_format,
        output_path=str(_default_report_path(target, normalized_format, root, template_kind)),
        template=template_kind,
    )
    if requested == "pdf":
        from vulnclaw.report.pdf_exporter import export_pdf

        pdf_path = Path(path).with_suffix(".pdf")
        export_pdf(
            Path(path).read_text(encoding="utf-8"),
            pdf_path,
            title=f"VulnClaw Report - {target}",
        )
        if output_path:
            import shutil

            destination = resolve_report_output_path(output_path, "pdf")
            shutil.copyfile(pdf_path, destination)
            return str(destination)
        return str(pdf_path.resolve())
    if output_path:
        destination = resolve_report_output_path(output_path, requested)
        destination.write_text(Path(path).read_text(encoding="utf-8"), encoding="utf-8")
        return str(destination)
    return str(Path(path).resolve())


def read_report_content(path: str) -> ReportContentView:
    """Read a report file for preview, limited to the sessions directory."""
    candidate = resolve_report_path(path)
    suffix = candidate.suffix.lower()
    if suffix == ".html":
        kind = "html"
    elif suffix == ".pdf":
        kind = "pdf"
    elif suffix == ".json":
        kind = "json"
    elif suffix == ".sarif":
        kind = "sarif"
    else:
        kind = "markdown"
    content = "" if suffix == ".pdf" else candidate.read_text(encoding="utf-8")
    return ReportContentView(path=str(candidate), kind=kind, content=content)


def resolve_report_path(path: str) -> Path:
    """Resolve a report path while preventing access outside sessions dir."""
    ensure_dirs()
    candidate = Path(path).resolve()
    if not any(
        root.resolve() in candidate.parents or candidate == root.resolve()
        for root in _report_roots()
    ):
        raise PermissionError(f"Report path is outside report roots: {candidate}")
    if not candidate.exists():
        raise FileNotFoundError(f"Report not found: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Report is not a file: {candidate}")
    if candidate.suffix.lower() not in {".md", ".html", ".pdf", ".json", ".sarif"}:
        raise PermissionError(f"Unsupported report file type: {candidate.suffix}")

    return candidate


def resolve_report_output_path(path: str, report_format: str) -> Path:
    """Resolve a web report output path under sessions dir."""
    ensure_dirs()
    requested = report_format.lower()
    expected_suffix = ".html" if requested == "html" else ".pdf" if requested == "pdf" else ".md"
    destination = Path(path)
    if not destination.name:
        raise PermissionError("Report output path must include a file name")
    if destination.suffix.lower() != expected_suffix:
        raise PermissionError(f"Report output path must end with {expected_suffix}")

    candidate = destination.resolve()
    if not any(
        root.resolve() in candidate.parents or candidate == root.resolve()
        for root in _report_roots()
    ):
        raise PermissionError(f"Report output path is outside report roots: {candidate}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate
