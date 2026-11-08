"""FastAPI app entry for the VulnClaw Web UI backend."""

from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Optional

from vulnclaw import __version__
from vulnclaw.encoding import configure_stdio_utf8
from vulnclaw.web.auth import AuthMiddleware, attach_session_cookie, verify_token
from vulnclaw.web.schemas import (
    ConfigUpdateRequest,
    FindingTriageRequest,
    IntegrationDeliveryView,
    IntegrationDispatchRequest,
    IntegrationUpsertRequest,
    MCPToggleRequest,
    ProjectCreateRequest,
    ProjectTargetRequest,
    ProviderModelsRequest,
    ReportGenerateRequest,
    ScheduleUpsertRequest,
    TaskCreateRequest,
)
from vulnclaw.web.services.config_service import get_public_config, update_public_config
from vulnclaw.web.services.constraint_audit_service import (
    export_constraint_audit,
    get_constraint_audit,
)
from vulnclaw.web.services.finding_service import list_findings, update_finding
from vulnclaw.web.services.integration_service import (
    delete_integration,
    dispatch_integrations,
    list_deliveries,
    list_integrations,
    retry_last_failed_delivery,
    save_integration,
    test_integration,
)
from vulnclaw.web.services.mcp_control_service import toggle_mcp_server
from vulnclaw.web.services.mcp_service import get_mcp_diagnostics
from vulnclaw.web.services.plugin_service import get_plugin, list_plugins
from vulnclaw.web.services.project_service import (
    assign_target,
    create_project,
    get_project,
    list_projects,
)
from vulnclaw.web.services.provider_service import fetch_models, get_provider_presets
from vulnclaw.web.services.report_service import (
    generate_target_report,
    list_reports,
    read_report_content,
    resolve_report_path,
)
from vulnclaw.web.services.run_service import get_run, list_runs
from vulnclaw.web.services.schedule_service import (
    delete_schedule,
    list_schedules,
    run_due,
    save_schedule,
)
from vulnclaw.web.services.target_service import (
    clear_target,
    get_diff,
    get_preview,
    get_snapshots,
    get_target,
    get_target_raw,
    list_targets,
    rollback_target,
)
from vulnclaw.web.services.task_service import start_task
from vulnclaw.web.stream import encode_heartbeat, encode_sse
from vulnclaw.web.task_manager import WebTaskManager

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import (
        FileResponse,
        JSONResponse,
        RedirectResponse,
        Response,
        StreamingResponse,
    )
    from starlette.middleware.base import BaseHTTPMiddleware

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in CLI dry-run and tests
    FastAPI = None  # type: ignore[assignment]
    HTTPException = RuntimeError  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    FileResponse = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    RedirectResponse = None  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]
    BaseHTTPMiddleware = object  # type: ignore[assignment,misc]
    FASTAPI_AVAILABLE = False


configure_stdio_utf8()

STATIC_DIR = Path(__file__).with_name("static")
#: Vite 构建产物，随 wheel / sdist 一起分发，源码树与安装后的路径一致。
FRONTEND_DIST_DIR = Path(__file__).with_name("dist")
task_manager = WebTaskManager()
_STARTED_AT = time.monotonic()


def resolve_web_index() -> Path:
    """Return the preferred index file for the Web UI."""
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return dist_index
    return STATIC_DIR / "index.html"


def resolve_web_asset(path: str) -> Path | None:
    """Resolve a frontend asset, returning ``None`` for missing files.

    SPA fallback is only correct for extension-less routes. Returning
    ``index.html`` for a missing ``/assets/*.js`` makes the browser parse HTML
    as JavaScript and hides deployment mistakes behind a 200 response.
    """
    normalized = path.replace("\\", "/").lstrip("/").strip()
    if not normalized:
        return resolve_web_index()

    for base_dir in (FRONTEND_DIST_DIR, STATIC_DIR):
        candidate = (base_dir / normalized).resolve()
        base_resolved = base_dir.resolve()
        if base_resolved in candidate.parents and candidate.is_file():
            return candidate

    if "." in Path(normalized).name:
        return None
    return resolve_web_index()


def _serve_spa(request, file_path: Path):  # type: ignore[no-untyped-def]
    """Serve a frontend file, trading a ``?token=`` query for a session cookie.

    The browser UI cannot send a bearer header (see :mod:`vulnclaw.web.auth`),
    so opening the printed ``/?token=<token>`` URL once is what authenticates
    the session. The token is redirected straight back out of the address bar
    so it does not linger in history or leak through ``Referer``.
    """
    token = request.query_params.get("token", "")
    if token and verify_token(token):
        response = RedirectResponse(
            str(request.url.remove_query_params("token")), status_code=303
        )
        attach_session_cookie(response, token)
        return response
    return FileResponse(file_path)


@contextmanager
def _report_fs_errors():
    """Map report failures onto HTTP responses.

    Missing file -> 404, denied path -> 403, and a missing optional PDF extra ->
    400 with the install hint instead of a bare 500.
    """
    try:
        yield
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def create_app():
    """Create the Web UI backend app."""
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed. Install the web extra first: pip install vulnclaw[web]"
        )

    async def _schedule_loop():
        while True:
            try:
                from vulnclaw.task_service import TaskCreateRequest, TaskOptions

                def runner(job):
                    try:
                        start_task(
                            task_manager,
                            TaskCreateRequest(
                                command=job.command,
                                target=job.target,
                                options=TaskOptions(**job.options),
                            ),
                        )
                    except Exception:
                        return

                run_due(runner)
            except Exception:
                pass
            await asyncio.sleep(5)

    @asynccontextmanager
    async def lifespan(_app):
        scheduler_task = asyncio.create_task(_schedule_loop())
        try:
            yield
        finally:
            scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler_task
            await task_manager.shutdown()

    app = FastAPI(title="VulnClaw Web UI", version=__version__, lifespan=lifespan)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuthMiddleware)

    @app.get("/api/health")
    async def health():
        ui_state = "built" if (FRONTEND_DIST_DIR / "index.html").exists() else "fallback"
        return {
            "status": "ok",
            "service": "vulnclaw-web",
            "version": __version__,
            "uptime_seconds": round(time.monotonic() - _STARTED_AT, 3),
            "ui": ui_state,
            "tasks": {
                "running": task_manager.running_count(),
                "queued": task_manager.queued_count(),
            },
        }

    @app.get("/api/config")
    async def config_view():
        return get_public_config().model_dump(mode="json")

    @app.get("/api/mcp")
    async def mcp_view():
        return get_mcp_diagnostics().model_dump(mode="json")

    @app.post("/api/mcp/toggle")
    async def mcp_toggle(request: MCPToggleRequest):
        result = toggle_mcp_server(request.name, request.enabled)
        if result is None:
            raise HTTPException(status_code=404, detail="MCP server not found")
        return result

    @app.get("/api/constraint-audit")
    async def constraint_audit_view():
        return get_constraint_audit().model_dump(mode="json")

    @app.post("/api/config")
    async def config_update(request: ConfigUpdateRequest):
        return update_public_config(request).model_dump(mode="json")

    @app.get("/api/audit/export")
    async def audit_export(format: str = "jsonl"):
        try:
            content, media_type = export_constraint_audit(format)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        suffix = "csv" if format == "csv" else "jsonl"
        return Response(
            content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="vulnclaw-audit.{suffix}"'
            },
        )

    @app.get("/api/schedules")
    async def schedules_view():
        return [item.model_dump(mode="json") for item in list_schedules()]

    @app.post("/api/schedules")
    async def schedule_save(request: ScheduleUpsertRequest):
        return save_schedule(request).model_dump(mode="json")

    @app.delete("/api/schedules/{name}")
    async def schedule_delete(name: str):
        if not delete_schedule(name):
            raise HTTPException(status_code=404, detail="Schedule not found")
        return {"status": "ok", "name": name}

    @app.post("/api/schedules/run-due")
    async def schedule_run_due():
        from vulnclaw.task_service import TaskCreateRequest, TaskOptions

        def runner(job):
            try:
                start_task(
                    task_manager,
                    TaskCreateRequest(
                        command=job.command,
                        target=job.target,
                        options=TaskOptions(**job.options),
                    ),
                )
            except Exception:
                return

        return [item.model_dump(mode="json") for item in run_due(runner)]

    @app.get("/api/integrations")
    async def integrations_view():
        return [item.model_dump(mode="json") for item in list_integrations()]

    @app.post("/api/integrations")
    async def integration_save(request: IntegrationUpsertRequest):
        try:
            item = save_integration(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return item.model_dump(mode="json")

    @app.delete("/api/integrations/{name}")
    async def integration_delete(name: str):
        if not delete_integration(name):
            raise HTTPException(status_code=404, detail="Integration not found")
        return {"status": "ok", "name": name}

    @app.post("/api/integrations/dispatch")
    async def integration_dispatch(request: IntegrationDispatchRequest):
        results = await asyncio.to_thread(
            dispatch_integrations,
            request.target,
            request.run_name,
            request.findings,
        )
        return [item.__dict__ for item in results]

    @app.get("/api/integrations/deliveries")
    async def integration_deliveries(name: str | None = None, limit: int = 50):
        return [
            item.model_dump(mode="json")
            for item in await asyncio.to_thread(list_deliveries, name, limit)
        ]

    @app.post("/api/integrations/{name}/test")
    async def integration_test(name: str):
        result = await asyncio.to_thread(test_integration, name)
        if result is None:
            raise HTTPException(status_code=404, detail="Integration not found")
        return IntegrationDeliveryView(**result.__dict__).model_dump(mode="json")

    @app.post("/api/integrations/{name}/retry")
    async def integration_retry(name: str):
        result = await asyncio.to_thread(retry_last_failed_delivery, name)
        if result is None:
            raise HTTPException(
                status_code=404, detail="No failed, retryable delivery for this integration"
            )
        return IntegrationDeliveryView(**result.__dict__).model_dump(mode="json")

    @app.get("/api/plugins")
    async def plugins_view(include_external: bool = True):
        return await asyncio.to_thread(list_plugins, include_external=include_external)

    @app.get("/api/plugins/{plugin_id}")
    async def plugin_detail(plugin_id: str):
        item = await asyncio.to_thread(get_plugin, plugin_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Plugin not found")
        return item

    @app.get("/api/findings")
    async def findings_view(target: str):
        return [item.model_dump(mode="json") for item in list_findings(target)]

    @app.post("/api/findings/triage")
    async def finding_triage(request: FindingTriageRequest):
        try:
            item = update_finding(
                request.target,
                request.finding_key,
                triage_status=request.triage_status,
                note=request.note,
                assignee=request.assignee,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if item is None:
            raise HTTPException(status_code=404, detail="Target or finding not found")
        return item.model_dump(mode="json")

    @app.get("/api/providers")
    async def providers_view():
        return get_provider_presets().model_dump(mode="json")

    @app.post("/api/provider-models")
    async def provider_models_view(request: ProviderModelsRequest):
        from vulnclaw.offline import is_offline

        if is_offline():
            raise HTTPException(status_code=400, detail="Offline mode: provider probes are disabled")
        return fetch_models(request).model_dump(mode="json")

    @app.get("/api/tasks")
    async def tasks(project: Optional[str] = None):
        records = task_manager.list_tasks()
        if project is not None:
            if project == "":
                records = [item for item in records if not item.project_id]
            else:
                records = [item for item in records if item.project_id == project]
        return [item.model_dump(mode="json") for item in records]

    @app.post("/api/tasks/run")
    async def create_task(request: TaskCreateRequest):
        try:
            task_id = start_task(task_manager, request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        record = task_manager.get_task(task_id)
        return record.model_dump(mode="json") if record else {"task_id": task_id}

    @app.get("/api/tasks/{task_id}")
    async def task_detail(task_id: str):
        record = task_manager.get_task(task_id)
        if not record:
            raise HTTPException(status_code=404, detail="Task not found")
        return record.model_dump(mode="json")

    @app.post("/api/tasks/{task_id}/stop")
    async def stop_task(task_id: str):
        if not task_manager.get_task(task_id):
            raise HTTPException(status_code=404, detail="Task not found")
        ok = await task_manager.stop_task(task_id)
        if not ok:
            raise HTTPException(status_code=409, detail="Task already finished")
        return {"status": "stopped", "task_id": task_id}

    @app.get("/api/tasks/{task_id}/stream")
    async def stream_task(task_id: str, request: Request):
        if not task_manager.get_task(task_id):
            raise HTTPException(status_code=404, detail="Task not found")
        raw_cursor = (
            request.headers.get("last-event-id")
            or request.query_params.get("last_event_id")
            or "0"
        )
        try:
            after_seq = max(0, int(raw_cursor))
        except ValueError:
            after_seq = 0

        async def event_iter():
            async for item in task_manager.stream_events(task_id, after_seq=after_seq):
                yield encode_heartbeat() if item is None else encode_sse(item)

        return StreamingResponse(
            event_iter(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/targets")
    async def targets():
        return [item.model_dump(mode="json") for item in list_targets()]

    @app.get("/api/targets/{target:path}/raw")
    async def target_raw(target: str):
        raw = get_target_raw(target)
        if not raw:
            raise HTTPException(status_code=404, detail="Target not found")
        return JSONResponse(raw)

    @app.get("/api/target-preview/{target:path}")
    async def target_preview(target: str, snapshot_id: str | None = None):
        item = get_preview(target, snapshot_id=snapshot_id)
        if not item:
            raise HTTPException(status_code=404, detail="Target or snapshot not found")
        return item.model_dump(mode="json")

    @app.get("/api/targets/{target:path}/snapshots")
    async def target_snapshots(target: str):
        return [item.model_dump(mode="json") for item in get_snapshots(target)]

    @app.get("/api/target-diff/{target:path}")
    async def target_diff(target: str, from_snapshot_id: str, to_snapshot_id: str | None = None):
        item = get_diff(target, from_snapshot_id=from_snapshot_id, to_snapshot_id=to_snapshot_id)
        if not item:
            raise HTTPException(status_code=404, detail="Snapshot or target state not found")
        return item.model_dump(mode="json")

    @app.post("/api/targets/{target:path}/rollback")
    async def target_rollback(target: str, payload: dict):
        snapshot_id = str(payload.get("snapshot_id", "")).strip()
        if not snapshot_id:
            raise HTTPException(status_code=400, detail="snapshot_id is required")
        if not rollback_target(target, snapshot_id):
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {"status": "ok", "target": target, "snapshot_id": snapshot_id}

    @app.delete("/api/targets/{target:path}")
    async def target_clear(target: str):
        if not clear_target(target):
            raise HTTPException(status_code=404, detail="Target not found")
        return {"status": "ok", "target": target}

    @app.get("/api/targets/{target:path}")
    async def target_detail(target: str):
        item = get_target(target)
        if not item:
            raise HTTPException(status_code=404, detail="Target not found")
        return item.model_dump(mode="json")

    @app.get("/api/projects")
    async def projects():
        return [item.model_dump(mode="json") for item in list_projects()]

    @app.post("/api/projects")
    async def project_create(request: ProjectCreateRequest):
        try:
            item = create_project(
                request.name,
                customer=request.customer,
                scope=request.scope,
                targets=request.targets,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return item.model_dump(mode="json")

    @app.get("/api/projects/{slug}")
    async def project_detail(slug: str):
        item = get_project(slug)
        if item is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return item.model_dump(mode="json")

    @app.post("/api/projects/{slug}/targets")
    async def project_add_target(slug: str, request: ProjectTargetRequest):
        item = assign_target(slug, request.target)
        if item is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return item.model_dump(mode="json")

    @app.get("/api/runs")
    async def runs():
        return [item.model_dump(mode="json") for item in list_runs()]

    @app.get("/api/runs/{run_name}")
    async def run_detail(run_name: str):
        item = get_run(run_name)
        if item is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return item.model_dump(mode="json")

    @app.get("/api/reports")
    async def reports():
        return list_reports()

    @app.get("/api/reports/content")
    async def report_content(path: str):
        with _report_fs_errors():
            content = read_report_content(path)
        return content.model_dump(mode="json")

    @app.get("/api/reports/download")
    async def report_download(path: str):
        with _report_fs_errors():
            report_path = resolve_report_path(path)
        suffix = report_path.suffix.lower()
        if suffix == ".html":
            media_type = "text/html"
        elif suffix in {".json", ".sarif"}:
            media_type = "application/json"
        else:
            media_type = "text/markdown"
        return FileResponse(report_path, media_type=media_type, filename=report_path.name)

    @app.post("/api/reports/target")
    async def report_target(request: ReportGenerateRequest):
        try:
            with _report_fs_errors():
                path = generate_target_report(
                    request.target,
                    request.output_path,
                    request.report_format,
                    request.template,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "path": path}

    @app.get("/")
    async def index(request: Request):
        return _serve_spa(request, resolve_web_index())

    @app.get("/{full_path:path}")
    async def frontend_routes(full_path: str, request: Request):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        asset = resolve_web_asset(full_path)
        if asset is None:
            raise HTTPException(status_code=404, detail="Not found")
        return _serve_spa(request, asset)

    return app


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add conservative browser security headers for the local Web UI."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-src 'self' about: data: blob:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        return response
