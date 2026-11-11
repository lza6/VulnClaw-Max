#!/usr/bin/env python3
"""Web UI soak runner: tasks, SSE reconnects, and resource samples.

Uses only codescan tasks so the run is deterministic, local, and free of LLM or
external-network calls. Start with a short duration for a smoke test:

    python scripts/soak_web.py --duration 60 --interval 2 --clients 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _rss_mb() -> float | None:
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except ImportError:
        return None


def _child_processes() -> list[dict[str, object]]:
    """Snapshot live descendants (MCP stdio servers, npx, etc.)."""
    try:
        import psutil
    except ImportError:
        return []
    parent = psutil.Process()
    children = []
    for child in parent.children(recursive=True):
        try:
            if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                children.append({"pid": child.pid, "name": child.name()})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return children


def _sample() -> dict[str, object]:
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rss_mb": _rss_mb(),
        "threads": threading.active_count(),
    }


async def _sse_client(
    base: str, task_id: str, stop: asyncio.Event, reconnect_after: float = 60.0
) -> dict[str, object]:
    received = 0
    reconnects = 0
    last_id = 0
    while not stop.is_set():
        try:
            headers = {"Last-Event-ID": str(last_id)} if last_id else {}
            connection_started = time.monotonic()
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                async with client.stream(
                    "GET", f"{base}/api/tasks/{task_id}/stream", headers=headers
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("id: "):
                            last_id = int(line[4:])
                        elif line.startswith("event: "):
                            event_name = line[7:].strip()
                            received += 1
                            if event_name in {
                                "task_completed",
                                "task_failed",
                                "task_stopped",
                                "task_interrupted",
                            }:
                                return {
                                    "received": received,
                                    "reconnects": reconnects,
                                    "last_id": last_id,
                                }
                        if stop.is_set():
                            return {
                                "received": received,
                                "reconnects": reconnects,
                                "last_id": last_id,
                            }
                        if reconnect_after > 0 and time.monotonic() - connection_started >= reconnect_after:
                            break
            reconnects += 1
        except Exception:
            reconnects += 1
            await asyncio.sleep(0.5)
    return {"received": received, "reconnects": reconnects, "last_id": last_id}


async def _run(args: argparse.Namespace) -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="vulnclaw-soak-"))
    config_dir = temp_root / "config"
    config_dir.mkdir()
    sample_dir = temp_root / "sample"
    sample_dir.mkdir()
    (sample_dir / "app.py").write_text(
        "import subprocess\n\ndef run(user_input):\n    subprocess.run(user_input, shell=True)\n",
        encoding="utf-8",
    )

    os.environ["VULNCLAW_CONFIG_DIR"] = str(config_dir)
    children_before = _child_processes()

    from vulnclaw.web.app import create_app

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error")
    )
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    for _ in range(100):
        try:
            async with httpx.AsyncClient(timeout=1) as probe:
                if (await probe.get(f"{base}/api/health")).status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(0.1)

    samples: list[dict[str, object]] = []
    task_ids: list[str] = []
    stop = asyncio.Event()
    sse_tasks: list[asyncio.Task] = []
    started = time.monotonic()
    final_states: list[str] = []
    children_after: list[dict[str, object]] = []
    client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    try:
        while time.monotonic() - started < args.duration:
            response = await client.post(
                f"{base}/api/tasks/run",
                json={"command": "codescan", "target": str(sample_dir)},
            )
            if response.status_code == 200:
                task_ids.append(response.json()["task_id"])
            if len(task_ids) >= args.clients and not sse_tasks and task_ids:
                for task_id in task_ids[-args.clients :]:
                    sse_tasks.append(
                        asyncio.create_task(
                            _sse_client(base, task_id, stop, args.sse_reconnect_seconds)
                        )
                    )
            samples.append(_sample())
            await asyncio.sleep(args.interval)
    finally:
        stop.set()
        for task in sse_tasks:
            task.cancel()
        await asyncio.gather(*sse_tasks, return_exceptions=True)
        # Wait for all submitted tasks to reach a terminal state.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            final_states = []
            for task_id in task_ids:
                response = await client.get(f"{base}/api/tasks/{task_id}", timeout=2)
                if response.status_code == 404:
                    final_states.append("pruned")
                else:
                    final_states.append(response.json().get("status"))
            if all(
                state in {"completed", "failed", "stopped", "interrupted", "pruned"}
                for state in final_states
            ):
                break
            await asyncio.sleep(0.5)
        await client.aclose()
        server.should_exit = True
        await asyncio.sleep(2.0)
        children_after = _child_processes()

    rss_values = [float(item["rss_mb"]) for item in samples if item["rss_mb"] is not None]
    rss_start = rss_values[0] if rss_values else None
    rss_end = rss_values[-1] if rss_values else None
    rss_growth_pct = (
        round((rss_end - rss_start) / rss_start * 100.0, 2)
        if rss_start and rss_end is not None
        else None
    )
    report = {
        "duration_seconds": round(time.monotonic() - started, 1),
        "tasks_submitted": len(task_ids),
        "samples": samples,
        "rss_start_mb": rss_start,
        "rss_end_mb": rss_end,
        "rss_peak_mb": max(rss_values) if rss_values else None,
        "rss_median_mb": round(statistics.median(rss_values), 1) if rss_values else None,
        "rss_growth_pct": rss_growth_pct,
        "final_states": final_states,
        "children_before": children_before,
        "children_after": children_after,
    }
    failures: list[str] = []
    if report["duration_seconds"] >= 60:
        if rss_growth_pct is not None and rss_growth_pct > args.max_rss_growth:
            failures.append(f"rss_growth_pct {rss_growth_pct} > {args.max_rss_growth}")
    if any(
        state not in {"completed", "failed", "stopped", "interrupted", "pruned"}
        for state in final_states
    ):
        failures.append(f"non-terminal tasks remain: {final_states}")
    if len(children_after) > args.max_remaining_children:
        failures.append(f"child processes remain: {children_after}")
    report["assertions"] = {"ok": not failures, "failures": failures}

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.assert_ and failures:
        print("soak assertions failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="VulnClaw Web UI soak runner")
    parser.add_argument("--duration", type=int, default=3600, help="seconds to run")
    parser.add_argument("--interval", type=float, default=5.0, help="task submission interval")
    parser.add_argument("--clients", type=int, default=3, help="concurrent SSE clients")
    parser.add_argument(
        "--sse-reconnect-seconds",
        type=float,
        default=60.0,
        help="proactively reconnect each SSE client after this many seconds (0 = never)",
    )
    parser.add_argument("--output", default="", help="write the JSON report to this path")
    parser.add_argument("--assert", dest="assert_", action="store_true", help="fail on regressions")
    parser.add_argument("--max-rss-growth", type=float, default=10.0, help="RSS growth ceiling in percent")
    parser.add_argument(
        "--max-remaining-children",
        type=int,
        default=0,
        help="allowed live child processes after shutdown",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
