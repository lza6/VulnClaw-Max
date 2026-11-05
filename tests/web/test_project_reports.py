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
