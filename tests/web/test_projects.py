"""Project workspace records isolate targets and report directories."""

from __future__ import annotations

import pytest


def _service(monkeypatch, tmp_path):
    import vulnclaw.web.services.project_service as service

    monkeypatch.setattr(service, "PROJECTS_DIR", tmp_path)
    return service


def test_create_list_and_get_project(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)

    created = service.create_project(
        "Acme Web", customer="Acme", scope="example.com", targets=["https://example.com"]
    )
    assert created.slug == "acme-web"
    assert created.targets == ["https://example.com"]

    projects = service.list_projects()
    assert [item.slug for item in projects] == ["acme-web"]
    assert service.get_project("acme-web").name == "Acme Web"
    assert (tmp_path / "acme-web" / "reports").is_dir()


def test_duplicate_project_is_rejected(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.create_project("Acme Web")
    with pytest.raises(ValueError):
        service.create_project("Acme Web")


def test_assign_target_is_idempotent(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.create_project("Acme Web")

    service.assign_target("acme-web", "https://example.com")
    project = service.assign_target("acme-web", "https://example.com")

    assert project is not None
    assert project.targets == ["https://example.com"]


def test_project_slug_cannot_escape_root(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    assert service.get_project("../secret") is None
    assert service.assign_target("..\\secret", "https://example.com") is None


def test_project_name_without_ascii_gets_generated_slug(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    project = service.create_project("客户项目")
    assert project.slug.startswith("project-")
    assert service.get_project(project.slug) is not None


def test_find_project_for_target(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.create_project("Acme", targets=["https://example.com"])
    assert service.find_project_for_target("https://example.com") == "acme"
    assert service.find_project_for_target("https://other.example") is None


def test_prepare_task_reads_project_env(monkeypatch):
    from vulnclaw.task_service import TaskCreateRequest, prepare_task

    monkeypatch.setenv("VULNCLAW_PROJECT", "acme")
    request = TaskCreateRequest(command="recon", target="example.com")
    prepare_task(request)
    assert request.options.project == "acme"


def test_target_moves_between_projects(monkeypatch, tmp_path):
    import vulnclaw.web.services.project_service as service

    monkeypatch.setattr(service, "PROJECTS_DIR", tmp_path / "projects")
    service.create_project("Acme", targets=["https://example.com"])
    service.create_project("Other")

    moved = service.assign_target("other", "https://example.com")

    assert moved is not None
    assert service.find_project_for_target("https://example.com") == "other"
    assert "https://example.com" not in service.get_project("acme").targets
    assert "https://example.com" in service.get_project("other").targets


def test_unassign_target_removes_from_project(monkeypatch, tmp_path):
    import vulnclaw.web.services.project_service as service

    monkeypatch.setattr(service, "PROJECTS_DIR", tmp_path / "projects")
    service.create_project("Acme", targets=["https://example.com"])

    assert service.unassign_target("https://example.com") is True
    assert service.find_project_for_target("https://example.com") is None
    assert service.get_project("acme").targets == []


def test_target_list_can_filter_by_project(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.target_service as target_service
    from vulnclaw.agent.context import SessionState

    targets_dir = tmp_path / "targets"
    monkeypatch.setattr(store, "TARGETS_DIR", targets_dir)
    monkeypatch.setattr(target_service, "TARGETS_DIR", targets_dir)
    monkeypatch.setattr(project_service, "PROJECTS_DIR", tmp_path / "projects")

    for target in ("https://a.example", "https://b.example", "https://c.example"):
        store.save_target_state(target, SessionState(target=target), command="recon")
    project_service.create_project("Acme", targets=["https://a.example"])
    project_service.create_project("Other", targets=["https://b.example"])

    assert [item.target for item in target_service.list_targets(project="acme")] == ["https://a.example"]
    unassigned = {item.target for item in target_service.list_targets(project="")}
    assert unassigned == {"https://c.example"}
