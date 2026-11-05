"""Target listing must be fast and tolerate one corrupt state file."""

from __future__ import annotations

import json
import time

import pytest


def test_list_targets_skips_corrupt_file(monkeypatch, tmp_path):
    import vulnclaw.web.services.target_service as service

    monkeypatch.setattr(service, "TARGETS_DIR", tmp_path)
    for index in range(3):
        target_dir = tmp_path / f"t{index}"
        target_dir.mkdir()
        (target_dir / "state.json").write_text(
            json.dumps(
                {
                    "target": f"127.0.0.1:{index}",
                    "phase": "recon",
                    "schema_version": 2,
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )
    (tmp_path / "t1" / "state.json").write_text("{broken", encoding="utf-8")

    views = service.list_targets()

    assert len(views) == 2
    assert {view.target for view in views} == {"127.0.0.1:0", "127.0.0.1:2"}


def test_list_targets_truncates_before_parsing(monkeypatch, tmp_path):
    import vulnclaw.web.services.target_service as service

    monkeypatch.setattr(service, "TARGETS_DIR", tmp_path)
    for index in range(200):
        target_dir = tmp_path / f"t{index:03d}"
        target_dir.mkdir()
        (target_dir / "state.json").write_text(
            json.dumps(
                {
                    "target": f"127.0.0.1:{index}",
                    "phase": "recon",
                    "schema_version": 2,
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )

    started = time.perf_counter()
    views = service.list_targets(limit=20)
    elapsed = time.perf_counter() - started

    assert len(views) == 20
    assert elapsed < 0.5


def test_list_targets_limit_is_bounded():
    import vulnclaw.web.services.target_service as service

    with pytest.raises(ValueError):
        service.list_targets(limit=0)
