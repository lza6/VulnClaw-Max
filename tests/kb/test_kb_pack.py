"""KB offline pack/restore bundle round trip."""

from __future__ import annotations

import json

import pytest

from vulnclaw.kb.pack import (
    BUNDLE_VERSION,
    load_bundle,
    pack_kb,
    restore_kb,
    write_bundle,
)
from vulnclaw.kb.store import KnowledgeStore


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(store_dir=tmp_path / "kb")


def test_pack_restore_round_trip(store, tmp_path):
    store.add_entry(
        "cve",
        "CVE-TEST-0001",
        {"title": "Test CVE", "severity": "High", "description": "d"},
    )
    store.add_entry(
        "techniques",
        "tech-1",
        {"title": "技术一", "tags": ["recon"]},
    )

    bundle = pack_kb(store)
    assert bundle["entry_count"] == 2
    assert bundle["bundle_version"] == BUNDLE_VERSION

    target = KnowledgeStore(store_dir=tmp_path / "kb2")
    added, skipped = restore_kb(target, bundle)
    assert (added, skipped) == (2, 0)

    stats = target.get_stats()
    assert stats.get("cve") == 1
    assert stats.get("techniques") == 1
    restored = target.get_entry("cve", "CVE-TEST-0001")
    assert restored is not None
    assert restored["title"] == "Test CVE"


def test_restore_is_idempotent(store):
    store.add_entry("tools", "tool-1", {"title": "Tool"})
    bundle = pack_kb(store)

    first = restore_kb(store, bundle)
    second = restore_kb(store, bundle)
    assert first == (1, 0)
    assert second == (1, 0)
    assert store.get_stats()["tools"] == 1


def test_restore_rejects_newer_bundle_version(store):
    with pytest.raises(ValueError, match="newer"):
        restore_kb(store, {"bundle_version": BUNDLE_VERSION + 1, "entries": []})


def test_restore_skips_malformed_rows(store):
    added, skipped = restore_kb(
        store,
        {
            "bundle_version": BUNDLE_VERSION,
            "entries": [
                {"category": "cve", "id": "ok-1", "data": {"title": "fine"}},
                {"category": None, "id": "x", "data": {}},
                {"category": "cve", "id": "", "data": {}},
                {"category": "cve", "id": "no-data"},
            ],
        },
    )
    assert (added, skipped) == (1, 3)


def test_bundle_file_round_trip(store, tmp_path):
    store.add_entry("payloads", "p-1", {"title": "Payload"})
    bundle = pack_kb(store)
    destination = write_bundle(bundle, tmp_path / "bundle.json")

    loaded = load_bundle(destination)
    assert loaded["entry_count"] == 1

    # Plain json.load must succeed: the bundle is UTF-8 with CJK-safe ensure_ascii=False.
    raw = json.loads(destination.read_text(encoding="utf-8"))
    assert raw["entry_count"] == 1
