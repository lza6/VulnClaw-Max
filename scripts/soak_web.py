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
import socket
import statistics
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


def _sample() -> dict[str, object]:
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rss_mb": _rss_mb(),
        "threads": threading.active_count(),
    }


async def _sse_client(base: str, task_id: str, stop: asyncio.Event) -> dict[str, object]:
    received = 0
    reconnects = 0
    last_id = 0
    while not stop.is_set():
        try:
            headers = {"Last-Event-ID": str(last_id)} if last_id else {}
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                async with client.stream(
                    "GET", f"{base}/api/tasks/{task_id}/stream", headers=headers
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("id: "):
                            last_id = int(line[4:])
                        elif line.startswith("event: "):
                            received += 1
                        if stop.is_set():
                            return {
                                "received": received,
                                "reconnects": reconnects,
                                "last_id": last_id,
                            }
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

    import os

    os.environ["VULNCLAW_CONFIG_DIR"] = str(config_dir)

    from vulnclaw.web.app import create_app

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error")
    )
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    for _ in range(100):
        try:
            if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                break
        except Exception:
            pass
        await asyncio.sleep(0.1)

    samples: list[dict[str, object]] = []
    task_ids: list[str] = []
    stop = asyncio.Event()
    sse_tasks: list[asyncio.Task] = []
    started = time.monotonic()

    try:
        while time.monotonic() - started < args.duration:
            response = httpx.post(
                f"{base}/api/tasks/run",
                json={"command": "codescan", "target": str(sample_dir)},
                timeout=10,
            )
            if response.status_code == 200:
                task_ids.append(response.json()["task_id"])
            if len(task_ids) >= args.clients and not sse_tasks and task_ids:
                for task_id in task_ids[-args.clients :]:
                    sse_tasks.append(asyncio.create_task(_sse_client(base, task_id, stop)))
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
            states = [
                httpx.get(f"{base}/api/tasks/{task_id}", timeout=2).json().get("status")
                for task_id in task_ids
            ]
            if all(state in {"completed", "failed", "stopped", "interrupted"} for state in states):
                break
            await asyncio.sleep(0.5)
        server.should_exit = True
        await asyncio.sleep(0.5)

    rss_values = [float(item["rss_mb"]) for item in samples if item["rss_mb"] is not None]
    report = {
        "duration_seconds": round(time.monotonic() - started, 1),
        "tasks_submitted": len(task_ids),
        "samples": samples,
        "rss_start_mb": rss_values[0] if rss_values else None,
        "rss_end_mb": rss_values[-1] if rss_values else None,
        "rss_peak_mb": max(rss_values) if rss_values else None,
        "rss_median_mb": round(statistics.median(rss_values), 1) if rss_values else None,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="VulnClaw Web UI soak runner")
    parser.add_argument("--duration", type=int, default=3600, help="seconds to run")
    parser.add_argument("--interval", type=float, default=5.0, help="task submission interval")
    parser.add_argument("--clients", type=int, default=3, help="concurrent SSE clients")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
