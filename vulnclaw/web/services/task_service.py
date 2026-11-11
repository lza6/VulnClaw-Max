"""Task orchestration service for the Web UI backend."""

from __future__ import annotations

import asyncio
import logging

from vulnclaw.agent.core import AgentCore
from vulnclaw.config.settings import load_config
from vulnclaw.i18n import init_i18n
from vulnclaw.integrations.notify import build_run_notification
from vulnclaw.mcp.lifecycle import MCPLifecycleManager
from vulnclaw.task_service import execute_task, prepare_task
from vulnclaw.web.schemas import TaskCreateRequest
from vulnclaw.web.services.integration_service import notify_run_event
from vulnclaw.web.services.project_service import assign_target, get_project
from vulnclaw.web.task_manager import WebTaskManager

logger = logging.getLogger(__name__)


def start_task(manager: WebTaskManager, request: TaskCreateRequest) -> str:
    """Create and schedule a new task behind the manager's concurrency slot."""
    if request.options.project and get_project(request.options.project) is None:
        raise ValueError(f"Project not found: {request.options.project}")
    record = manager.create_task(request)
    if request.options.project:
        # Associate after the task exists so a failed create never moves a target
        # into a project that has no task referencing it.
        if assign_target(request.options.project, request.target) is None:
            manager.set_failed(record.task_id, f"Project not found: {request.options.project}")
            raise ValueError(f"Project not found: {request.options.project}")
    manager.set_queued(record.task_id)
    task = asyncio.create_task(_schedule_task(manager, record.task_id, request))
    manager.bind_runtime_task(record.task_id, task)
    return record.task_id


async def _schedule_task(
    manager: WebTaskManager, task_id: str, request: TaskCreateRequest
) -> None:
    await manager.acquire_slot()
    try:
        await _run_task(manager, task_id, request)
    finally:
        manager.release_slot()


async def _run_task(manager: WebTaskManager, task_id: str, request: TaskCreateRequest) -> None:
    mcp_manager = None
    try:
        config = load_config()
        # Web-triggered tasks (including persistent-cycle runs) build prompts and
        # reports outside the CLI, so the configured language must be resolved
        # here before any of that code runs — the CLI does this at its own
        # entrypoints, but this background/orchestrated path has no CLI to do it.
        init_i18n(config=config)
        mcp_manager = MCPLifecycleManager(config)
        mcp_manager.start_enabled_servers()
        agent = AgentCore(config, mcp_manager, console_output=False)

        def before_restore(_restore_result) -> None:
            if request.resume:
                manager.set_restoring(task_id, snapshot_id=request.snapshot_id)

        def on_restored(restore_result) -> None:
            manager.publish(
                task_id,
                "task_state_changed",
                {
                    "resume": True,
                    "snapshot_id": restore_result.snapshot_id,
                    "phase": restore_result.phase,
                    "resume_strategy": restore_result.resume_strategy,
                    "resume_reason": restore_result.resume_reason,
                },
            )

        def on_legacy_import(restore_result) -> None:
            manager.publish(
                task_id,
                "legacy_import",
                {
                    "target": restore_result.target,
                    "snapshot_id": restore_result.snapshot_id,
                },
            )

        execution = await execute_task(
            agent,
            prepare_task(request),
            before_restore=before_restore,
            on_restored=on_restored,
            on_legacy_import=on_legacy_import,
            before_action=lambda: manager.set_running(task_id),
            on_step=_build_step_callback(manager, task_id),
            on_cycle_step=_build_cycle_step_callback(manager, task_id),
            on_cycle_complete=_build_cycle_complete_callback(manager, task_id),
        )
        _publish_action_result(manager, task_id, execution.action_result)
        run_status = str(getattr(execution.run, "status", "completed") or "completed")
        if run_status == "interrupted":
            manager.set_interrupted(task_id, previous_status="running")
        elif run_status == "failed":
            message = str(execution.run.summary.get("error") or "Task failed")
            manager.set_failed(task_id, message)
            await _notify_run_terminal(
                manager, task_id, event="run.failed", status="failed", error=message
            )
        else:
            manager.set_completed(
                task_id, latest_message="Task finished", summary=execution.run.summary
            )
            await _notify_run_terminal(manager, task_id, event="run.completed", status="completed")
    except asyncio.CancelledError:
        manager.set_stopped(task_id)
        raise
    except Exception as exc:
        manager.set_failed(task_id, str(exc))
        await _notify_run_terminal(
            manager, task_id, event="run.failed", status="failed", error=str(exc)
        )
    finally:
        if mcp_manager is not None:
            mcp_manager.stop_all()
        manager.unbind_runtime_task(task_id)


async def _notify_run_terminal(
    manager: WebTaskManager,
    task_id: str,
    *,
    event: str,
    status: str,
    error: str = "",
) -> None:
    """Fan a terminal run event out to the webhooks subscribed to it.

    Delivery failures are logged by the integration service and never alter the
    task's own outcome: a broken relay must not turn a finished scan into a
    failed one.
    """
    record = manager.get_task(task_id)
    if record is None:
        return
    summary = record.summary.model_dump(mode="json") if record.summary else {}
    artifacts = summary.get("artifact_locations") or {}
    payload = build_run_notification(
        event=event,
        task_id=task_id,
        command=str(summary.get("command") or record.command),
        target=str(summary.get("target") or record.target),
        status=status,
        run_name=str(summary.get("run_name") or ""),
        findings_count=int(summary.get("findings_count") or 0),
        verified_count=int(summary.get("verified_count") or 0),
        pending_count=int(summary.get("pending_count") or 0),
        run_dir=str(summary.get("run_dir") or ""),
        reports_dir=str(artifacts.get("reports") or ""),
        error=error,
    )
    try:
        await asyncio.to_thread(notify_run_event, payload)
    except Exception as exc:
        logger.warning("Run notification dispatch failed for %s: %s", task_id, exc)


def _build_cycle_step_callback(manager: WebTaskManager, task_id: str):
    def on_cycle_step(round_num: int, cycle_num: int, result) -> None:
        manager.publish(
            task_id,
            "round_output",
            {
                "cycle": cycle_num,
                "round": round_num,
                "phase": result.phase,
                "text": result.output,
            },
        )
        manager.update_progress(task_id, phase=result.phase, message=(result.output or "")[:200])

    return on_cycle_step


def _build_cycle_complete_callback(manager: WebTaskManager, task_id: str):
    def on_cycle_complete(cycle_num: int, cycle_result) -> None:
        manager.publish(
            task_id,
            "cycle_completed",
            {
                "cycle": cycle_num,
                "new_findings": cycle_result.new_findings,
                "report_path": cycle_result.report_path,
            },
        )

    return on_cycle_complete


def _build_step_callback(manager: WebTaskManager, task_id: str):
    def _callback(round_num: int, result) -> None:
        manager.publish(
            task_id,
            "round_output",
            {
                "round": round_num,
                "phase": result.phase,
                "text": result.output,
            },
        )
        manager.update_progress(task_id, phase=result.phase, message=(result.output or "")[:200])

    return _callback


def _publish_action_result(manager: WebTaskManager, task_id: str, result) -> None:
    if isinstance(result, list) and result:
        result = result[-1]
    output = getattr(result, "output", "")
    if not output:
        return
    phase = getattr(result, "phase", None)
    manager.publish(task_id, "round_output", {"phase": phase, "text": output})
    manager.update_progress(task_id, phase=phase, message=output[:200])
