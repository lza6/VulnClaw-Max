"""Reports for project targets land under the project workspace."""

from __future__ import annotations

from pathlib import Path


def test_project_report_path(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.report_service as report_service
    from vulnclaw.agent.context import SessionState
    from vulnclaw.config.domain_models import VulnerabilityFinding

    projects = tmp_path / "projects"
    sessions = tmp_path / "sessions"
    monkeypatch.setattr(project_service, "PROJECTS_DIR", projects)
    monkeypatch.setattr(report_service, "PROJECTS_DIR", projects)
    monkeypatch.setattr(report_service, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path / "targets")

    project_service.create_project("Acme", targets=["https://example.com"])
    session = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(
        title="SQL Injection",
        severity="High",
        vuln_type="SQLi",
        description="confirmed",
    )
    finding.mark_verified(note="ok")
    session.add_finding(finding)
    store.save_target_state("https://example.com", session, command="scan")

    path = report_service.generate_target_report("https://example.com")

    assert "projects" in path
    assert "acme" in path
    assert "reports" in path
    assert any("acme/" in item["name"] for item in report_service.list_reports())


def test_generate_pdf_report(monkeypatch, tmp_path):
    import vulnclaw.report.pdf_exporter as pdf_exporter
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.report_service as report_service
    from vulnclaw.agent.context import SessionState
    from vulnclaw.config.domain_models import VulnerabilityFinding

    projects = tmp_path / "projects"
    sessions = tmp_path / "sessions"
    monkeypatch.setattr(project_service, "PROJECTS_DIR", projects)
    monkeypatch.setattr(report_service, "PROJECTS_DIR", projects)
    monkeypatch.setattr(report_service, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path / "targets")

    def fake_export(markdown, out_path, *, title=None):
        Path(out_path).write_bytes(b"%PDF-1.4 mock")
        return Path(out_path)

    monkeypatch.setattr(pdf_exporter, "export_pdf", fake_export)
    session = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(
        title="SQL Injection", severity="High", vuln_type="SQLi", description="confirmed"
    )
    finding.mark_verified(note="ok")
    session.add_finding(finding)
    store.save_target_state("https://example.com", session, command="scan")

    path = report_service.generate_target_report("https://example.com", report_format="pdf")

    assert path.endswith(".pdf")
    assert Path(path).read_bytes().startswith(b"%PDF")


def test_explicit_project_overrides_target_ownership(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.report_service as report_service
    from vulnclaw.agent.context import SessionState

    projects = tmp_path / "projects"
    monkeypatch.setattr(project_service, "PROJECTS_DIR", projects)
    monkeypatch.setattr(report_service, "PROJECTS_DIR", projects)
    monkeypatch.setattr(report_service, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path / "targets")

    project_service.create_project("Acme", targets=["https://example.com"])
    project_service.create_project("Other")
    store.save_target_state(
        "https://example.com", SessionState(target="https://example.com"), command="scan"
    )

    path = report_service.generate_target_report("https://example.com", project="other")

    assert "other" in path


def test_report_can_be_built_from_a_run_snapshot(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import vulnclaw.web.services.report_service as report_service
    from vulnclaw.agent.context import SessionState
    from vulnclaw.config.domain_models import VulnerabilityFinding

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    session = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(title="SQLi", severity="High", vuln_type="SQLi")
    finding.mark_verified(note="ok")
    session.add_finding(finding)
    (state_dir / "current.json").write_text(
        session.model_dump_json(), encoding="utf-8"
    )

    fake_context = SimpleNamespace(state_dir=lambda _target: state_dir)
    monkeypatch.setattr(report_service, "load_run_context", lambda _name: fake_context)
    monkeypatch.setattr(report_service, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(report_service, "PROJECTS_DIR", tmp_path / "projects")

    output = tmp_path / "sessions" / "report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    path = report_service.generate_target_report(
        "https://example.com", output_path=str(output), run_name="run-1"
    )

    assert path == str(output.resolve())
    assert "SQLi" in output.read_text(encoding="utf-8")
