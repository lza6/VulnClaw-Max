"""Plugin inventory API and the shipped example plugin package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

EXAMPLE_SRC = (
    Path(__file__).resolve().parents[2] / "examples" / "plugins" / "vulnclaw-plugin-demo" / "src"
)


@pytest.fixture
def client(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.app as web_app
    import vulnclaw.web.services.constraint_audit_service as audit_service
    import vulnclaw.web.services.integration_service as integration_service
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.run_service as run_service
    import vulnclaw.web.services.schedule_service as schedule_service

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(audit_service, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(run_service, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(project_service, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(integration_service, "INTEGRATIONS_FILE", tmp_path / "integrations.json")
    monkeypatch.setattr(schedule_service, "SCHEDULES_FILE", tmp_path / "schedules.json")

    return TestClient(web_app.create_app(), base_url="http://localhost", client=("127.0.0.1", 5555))


def _fake_entry_points(entries):

    return lambda group=None: entries


def test_inventory_lists_builtin_plugins(client, monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points([]))

    payload = client.get("/api/plugins").json()

    ids = {item["plugin_id"] for item in payload["plugins"]}
    assert {"builtin.web.headers", "builtin.web.jwt", "builtin.web.js_endpoints"} <= ids
    assert payload["errors"] == []
    headers = next(item for item in payload["plugins"] if item["plugin_id"] == "builtin.web.headers")
    assert headers["origin"] == "builtin"
    assert headers["stages"]


def test_broken_entry_point_is_reported_without_hiding_the_rest(client, monkeypatch):
    import importlib.metadata

    from vulnclaw.plugins import PluginResult, PluginStage, VulnPlugin

    class ExtraPlugin(VulnPlugin):
        plugin_id = "demo.extra"
        stages = (PluginStage.RECON,)

        def run(self, context):
            return PluginResult(plugin_id=self.plugin_id, stage=context.stage)

    class Entry:
        def __init__(self, name, loader):
            self.name = name
            self._loader = loader

        def load(self):
            return self._loader()

    def broken():
        raise ImportError("dependency missing")

    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        _fake_entry_points([Entry("extra", lambda: ExtraPlugin), Entry("broken", broken)]),
    )

    payload = client.get("/api/plugins").json()

    ids = {item["plugin_id"] for item in payload["plugins"]}
    assert "demo.extra" in ids
    external = next(item for item in payload["plugins"] if item["plugin_id"] == "demo.extra")
    assert external["origin"] == "external"
    assert payload["errors"] == [
        {"entry_point": "broken", "error": "dependency missing"}
    ]


def test_plugin_detail_returns_metadata_and_404s(client, monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points([]))

    detail = client.get("/api/plugins/builtin.web.jwt").json()
    assert detail["plugin_id"] == "builtin.web.jwt"
    assert client.get("/api/plugins/nope.missing").status_code == 404


def test_example_plugin_package_loads_and_flags_insecure_cookies(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLE_SRC))
    sys.modules.pop("vulnclaw_plugin_demo", None)

    from vulnclaw_plugin_demo import CookieFlagsPlugin

    from vulnclaw.plugins import PluginContext, PluginRegistry, PluginStage

    registry = PluginRegistry()
    registry.register(CookieFlagsPlugin)

    result = CookieFlagsPlugin().run(
        PluginContext(
            target="https://example.com",
            stage=PluginStage.DISCOVERY,
            options={
                "set_cookie": [
                    "sid=abc; Path=/",
                    "csrf=xyz; Path=/; Secure; HttpOnly; SameSite=Lax",
                ]
            },
        )
    )

    assert result.ok is True
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.evidence["set_cookie"] == "sid=abc; Path=/"
    assert finding.evidence["missing"] == ["Secure", "HttpOnly", "SameSite"]
    assert finding.risk.value == "medium"


def test_example_plugin_skips_without_input(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLE_SRC))
    sys.modules.pop("vulnclaw_plugin_demo", None)

    from vulnclaw_plugin_demo import CookieFlagsPlugin

    from vulnclaw.plugins import PluginContext, PluginStage

    result = CookieFlagsPlugin().run(PluginContext(stage=PluginStage.DISCOVERY))

    assert result.skipped is True
    assert result.ok is False
