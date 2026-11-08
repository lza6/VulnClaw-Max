"""Offline KB transfer: pack the local knowledge base into one JSON bundle
and restore it on a machine without network access.

The bundle is a single JSON document (entries + category counts) so it can be
carried over an air gap with plain file copy — no archive tooling required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vulnclaw.kb.store import KnowledgeStore

BUNDLE_VERSION = 1


def pack_kb(store: KnowledgeStore) -> dict[str, Any]:
    """Serialize the whole KB into a JSON-able bundle dict."""
    entries: list[dict[str, Any]] = []
    for entry in store.iter_all_entries():
        category = entry.get("_category")
        entry_id = entry.get("id")
        if not category or not entry_id:
            continue
        payload = {k: v for k, v in entry.items() if not k.startswith("_")}
        entries.append({"category": category, "id": entry_id, "data": payload})

    return {
        "bundle_version": BUNDLE_VERSION,
        "entry_count": len(entries),
        "entries": entries,
    }


def restore_kb(store: KnowledgeStore, bundle: dict[str, Any]) -> tuple[int, int]:
    """Write a packed bundle back into a store.

    Returns ``(added, skipped)``. Existing entries with the same id are
    overwritten (bundle wins) so repeated restores stay idempotent.
    """
    if int(bundle.get("bundle_version", 0)) > BUNDLE_VERSION:
        raise ValueError(
            f"bundle version {bundle.get('bundle_version')} is newer than supported {BUNDLE_VERSION}"
        )

    added = 0
    skipped = 0
    for item in bundle.get("entries", []):
        category = item.get("category")
        entry_id = item.get("id")
        data = item.get("data")
        if not category or not entry_id or not isinstance(data, dict):
            skipped += 1
            continue
        store.add_entry(str(category), str(entry_id), dict(data))
        added += 1
    return added, skipped


def write_bundle(bundle: dict[str, Any], destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


def load_bundle(source: Path) -> dict[str, Any]:
    bundle = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict) or "entries" not in bundle:
        raise ValueError(f"{source} is not a VulnClaw KB bundle")
    return bundle
