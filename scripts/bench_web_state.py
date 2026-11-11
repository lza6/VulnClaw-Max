"""Benchmark the Web task manager's hot paths.

Usage:
    python scripts/bench_web_state.py            # print JSON
    python scripts/bench_web_state.py --assert   # exit non-zero on regression

The numbers are deliberately measured in a temporary config directory and an
event loop, matching how uvicorn drives the manager.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Keep the benchmark out of the user's real ~/.vulnclaw.
_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="vulnclaw-bench-"))
os.environ["VULNCLAW_CONFIG_DIR"] = str(_TEMP_ROOT)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vulnclaw.web.task_manager as task_manager_module  # noqa: E402
from vulnclaw.task_service import TaskCreateRequest, TaskOptions  # noqa: E402
from vulnclaw.web.task_manager import WebTaskManager  # noqa: E402


async def _bench_publish(manager: WebTaskManager) -> float:
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="bench.example", options=TaskOptions())
    )
    started = time.perf_counter()
    for index in range(300):
        manager.publish(record.task_id, "bench_event", {"index": index})
    elapsed = time.perf_counter() - started
    manager._flush_save()
    return elapsed


async def _bench_create(manager: WebTaskManager) -> float:
    started = time.perf_counter()
    for index in range(300):
        manager.create_task(
            TaskCreateRequest(
                command="codescan",
                target=f"bench-{index}.example",
                options=TaskOptions(),
            )
        )
    elapsed = time.perf_counter() - started
    manager._flush_save()
    return elapsed


def _bench_targets(targets_dir: Path) -> float:
    import vulnclaw.web.services.target_service as target_service

    targets_dir.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "target": f"bench-{index}.example",
            "schema_version": 2,
            "phase": "recon",
            "findings_count": 0,
            "updated_at": f"2026-11-05T00:00:{index % 60:02d}",
        }
        for index in range(500)
    ]
    (targets_dir / "index.json").write_text(json.dumps(entries), encoding="utf-8")
    original = target_service.TARGETS_DIR
    target_service.TARGETS_DIR = targets_dir
    try:
        started = time.perf_counter()
        views = target_service.list_targets(limit=20)
        elapsed = time.perf_counter() - started
        if len(views) != 20:  # pragma: no cover - defensive sanity check
            raise RuntimeError(f"target benchmark expected 20 views, got {len(views)}")
        return elapsed
    finally:
        target_service.TARGETS_DIR = original


async def run() -> dict[str, float]:
    task_manager_module.WEB_TASKS_FILE = _TEMP_ROOT / "web_tasks.json"
    task_manager_module.WEB_EVENTS_DIR = _TEMP_ROOT / "events"
    manager = WebTaskManager(max_concurrent=1)
    return {
        "publish_300_seconds": await _bench_publish(manager),
        "create_300_seconds": await _bench_create(manager),
        "list_500_targets_seconds": _bench_targets(_TEMP_ROOT / "targets"),
        "web_tasks_bytes": (task_manager_module.WEB_TASKS_FILE).stat().st_size
        if task_manager_module.WEB_TASKS_FILE.exists()
        else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VulnClaw Web state benchmarks")
    parser.add_argument("--assert", dest="assert_", action="store_true", help="fail when a threshold is exceeded")
    args = parser.parse_args()

    results = asyncio.run(run())
    print(json.dumps(results, indent=2))

    thresholds = {
        "publish_300_seconds": 0.25,
        "create_300_seconds": 1.5,
        "list_500_targets_seconds": 0.15,
        "web_tasks_bytes": 500_000,
    }
    failures = [
        f"{key}={results[key]:.4f} > {limit}"
        for key, limit in thresholds.items()
        if results[key] > limit
    ]
    if args.assert_ and failures:
        print("threshold exceeded: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
