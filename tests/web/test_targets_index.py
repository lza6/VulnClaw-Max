"""Global target index keeps listing fast and falls back safely."""

from __future__ import annotations

import json
import time


def _setup(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.target_service as service

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path)
    monkeypatch.setattr(service, "TARGETS_DIR", tmp_path)
    return store, service


def test_save_updates_index_and_list_uses_it(monkeypatch, tmp_path):
    store, service = _setup(monkeypatch, tmp_path)
    from vulnclaw.agent.context import SessionState

    for index in range(3):
        state = SessionState(target=f"https://example{index}.com")
        store.save_target_state(state.target, state, command="recon")

    index_path = tmp_path / "index.json"
    assert index_path.exists()
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(entries) == 3

    views = service.list_targets()
    assert {view.target for view in views} == {
        "https://example0.com",
        "https://example1.com",
        "https://example2.com",
    }


def test_corrupt_index_falls_back_to_scan(monkeypatch, tmp_path):
    store, service = _setup(monkeypatch, tmp_path)
    from vulnclaw.agent.context import SessionState

    state = SessionState(target="https://example.com")
    store.save_target_state(state.target, state, command="recon")
    (tmp_path / "index.json").write_text("{broken", encoding="utf-8")

    views = service.list_targets()

    assert views[0].target == "https://example.com"


def test_listing_500_indexed_targets_is_fast(monkeypatch, tmp_path):
    _store, service = _setup(monkeypatch, tmp_path)
    entries = [
        {
            "target": f"127.0.0.1:{index}",
            "schema_version": 2,
            "phase": "recon",
            "findings_count": 0,
            "updated_at": f"2026-11-05T00:00:{index % 60:02d}",
        }
        for index in range(500)
    ]
    (tmp_path / "index.json").write_text(json.dumps(entries), encoding="utf-8")

    started = time.perf_counter()
    views = service.list_targets()
    elapsed = time.perf_counter() - started

    assert len(views) == 20
    assert elapsed < 0.1
