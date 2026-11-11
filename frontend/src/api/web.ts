import { TASK_EVENT_NAMES } from "./taskEvents";
import type {
  ConfigView,
  GCResult,
  StorageUsage,
  ConstraintAuditView,
  ConfigUpdateRequest,
  FindingTriageRequest,
  FindingView,
  IntegrationDeliveryLogView,
  IntegrationDeliveryResult,
  IntegrationUpsertRequest,
  IntegrationView,
  MCPDiagnosticsView,
  PluginInventoryView,
  ProviderModelsRequest,
  ProviderModelsResponse,
  ProvidersView,
  ProjectView,
  ReportListItem,
  ReportContentView,
  ReportTemplate,
  RunDetail,
  ScheduleUpsertRequest,
  ScheduleView,
  RunSummary,
  TargetPreviewView,
  TargetSnapshotView,
  TargetStateDiffView,
  TargetView,
  TaskCommand,
  TaskEvent,
  TaskOptions,
  TaskRecord,
} from "../types/api";

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(input, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch {
    throw new Error("Unable to reach the VulnClaw backend API. Start `vulnclaw web` and reconnect.");
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(
      detail
        ? `Request failed (${response.status}): ${detail}`
        : `Request failed (${response.status}). Try again or open advanced diagnostics.`,
    );
  }

  try {
    return await response.json() as T;
  } catch {
    throw new Error("The backend API returned non-JSON content. Confirm the backend was started with `vulnclaw web`.");
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await response.json() as { detail?: unknown; message?: unknown; error?: unknown; code?: unknown };
      const rawDetail = payload.detail ?? payload.message ?? payload.error;
      const code = payload.code;
      const detailStr = stringifyErrorValue(rawDetail);
      if (code) {
        return `[${stringifyErrorValue(code)}] ${detailStr}`;
      }
      return summarizeErrorDetail(detailStr);
    }
    const text = await response.text();
    if (text) {
      return summarizeErrorDetail(text);
    }
    return `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

function summarizeErrorDetail(value: string): string {
  const normalized = value
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return "";
  if (normalized.length <= 240) return normalized;
  return `${normalized.slice(0, 240)}...`;
}

function stringifyErrorValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function getConfig(): Promise<ConfigView> {
  return requestJson<ConfigView>("/api/config");
}

export function getMcpDiagnostics(): Promise<MCPDiagnosticsView> {
  return requestJson<MCPDiagnosticsView>("/api/mcp");
}

export function toggleMcpServer(
  name: string,
  enabled: boolean,
  allowedTools?: string[],
): Promise<{ name: string; enabled: boolean; allowed_tools: string[]; applies_to: string; running: boolean; tool_count: number }> {
  return requestJson("/api/mcp/toggle", {
    method: "POST",
    body: JSON.stringify({ name, enabled, allowed_tools: allowedTools }),
  });
}

export function getConstraintAudit(): Promise<ConstraintAuditView> {
  return requestJson<ConstraintAuditView>("/api/constraint-audit");
}

export function getStorage(): Promise<StorageUsage> {
  return requestJson<StorageUsage>("/api/storage");
}

export function runGc(payload: { older_than: number; keep_last: number; dry_run: boolean }): Promise<GCResult> {
  return requestJson<GCResult>("/api/gc", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAuditExportUrl(format: "jsonl" | "csv"): string {
  return `/api/audit/export?format=${format}`;
}

export function getAuditExportRequestInit(): RequestInit {
  return { method: "GET" };
}

export function updateConfig(payload: ConfigUpdateRequest): Promise<ConfigView> {
  return requestJson<ConfigView>("/api/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProviders(): Promise<ProvidersView> {
  return requestJson<ProvidersView>("/api/providers");
}

export function fetchProviderModels(payload: ProviderModelsRequest): Promise<ProviderModelsResponse> {
  return requestJson<ProviderModelsResponse>("/api/provider-models", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTasks(project?: string): Promise<TaskRecord[]> {
  const suffix = project === undefined ? "" : `?project=${encodeURIComponent(project)}`;
  return requestJson<TaskRecord[]>(`/api/tasks${suffix}`);
}

export function getTargets(): Promise<TargetView[]> {
  return requestJson<TargetView[]>("/api/targets");
}

export function getTarget(target: string): Promise<TargetView> {
  return requestJson<TargetView>(`/api/targets/${encodeURIComponent(target)}`);
}

export function getTargetSnapshots(target: string): Promise<TargetSnapshotView[]> {
  return requestJson<TargetSnapshotView[]>(`/api/targets/${encodeURIComponent(target)}/snapshots`);
}

export function getTargetPreview(target: string): Promise<TargetPreviewView> {
  return requestJson<TargetPreviewView>(`/api/target-preview/${encodeURIComponent(target)}`);
}

export function getTargetDiff(target: string, fromSnapshotId: string, toSnapshotId?: string): Promise<TargetStateDiffView> {
  const params = new URLSearchParams({ from_snapshot_id: fromSnapshotId });
  if (toSnapshotId) {
    params.set("to_snapshot_id", toSnapshotId);
  }
  return requestJson<TargetStateDiffView>(`/api/target-diff/${encodeURIComponent(target)}?${params.toString()}`);
}

export function getProjects(): Promise<ProjectView[]> {
  return requestJson<ProjectView[]>("/api/projects");
}

export function getFindings(target: string): Promise<FindingView[]> {
  return requestJson<FindingView[]>(`/api/findings?target=${encodeURIComponent(target)}`);
}

export function triageFinding(payload: FindingTriageRequest): Promise<FindingView> {
  return requestJson<FindingView>("/api/findings/triage", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getRuns(): Promise<RunSummary[]> {
  return requestJson<RunSummary[]>("/api/runs");
}

export function getRunDetail(runName: string): Promise<RunDetail> {
  return requestJson<RunDetail>(`/api/runs/${encodeURIComponent(runName)}`);
}

export function getReports(): Promise<ReportListItem[]> {
  return requestJson<ReportListItem[]>("/api/reports");
}

export function getReportContent(path: string): Promise<ReportContentView> {
  return requestJson<ReportContentView>(`/api/reports/content?path=${encodeURIComponent(path)}`);
}

export function getReportDownloadUrl(path: string): string {
  return `/api/reports/download?path=${encodeURIComponent(path)}`;
}

export function rollbackTarget(target: string, snapshotId: string): Promise<{ status: string; target: string; snapshot_id: string }> {
  return requestJson(`/api/targets/${encodeURIComponent(target)}/rollback`, {
    method: "POST",
    body: JSON.stringify({ snapshot_id: snapshotId }),
  });
}

export function clearTargetState(target: string): Promise<{ status: string; target: string }> {
  return requestJson(`/api/targets/${encodeURIComponent(target)}`, {
    method: "DELETE",
  });
}

export function generateTargetReport(
  target: string,
  reportFormat: "markdown" | "html" | "pdf" = "markdown",
  template: ReportTemplate = "pentest",
  project?: string,
  runName?: string,
): Promise<{ status: string; path: string }> {
  return requestJson("/api/reports/target", {
    method: "POST",
    body: JSON.stringify({
      target,
      report_format: reportFormat,
      template,
      project,
      run_name: runName,
    }),
  });
}

export function getIntegrations(): Promise<IntegrationView[]> {
  return requestJson<IntegrationView[]>("/api/integrations");
}

export function saveIntegration(payload: IntegrationUpsertRequest): Promise<IntegrationView> {
  return requestJson<IntegrationView>("/api/integrations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteIntegration(name: string): Promise<{ status: string; name: string }> {
  return requestJson(`/api/integrations/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export function testIntegration(name: string): Promise<IntegrationDeliveryResult> {
  return requestJson<IntegrationDeliveryResult>(`/api/integrations/${encodeURIComponent(name)}/test`, {
    method: "POST",
  });
}

export function getPlugins(): Promise<PluginInventoryView> {
  return requestJson<PluginInventoryView>("/api/plugins");
}

export function createTask(command: TaskCommand, target: string, resume: boolean, options: TaskOptions = {}): Promise<TaskRecord> {
  return requestJson<TaskRecord>("/api/tasks/run", {
    method: "POST",
    body: JSON.stringify({
      command,
      target,
      resume,
      options,
    }),
  });
}

export function resumeRun(run: RunDetail): Promise<TaskRecord> {
  const snapshotId = typeof run.resume?.last_snapshot_id === "string" ? run.resume.last_snapshot_id : undefined;
  return requestJson<TaskRecord>("/api/tasks/run", {
    method: "POST",
    body: JSON.stringify({
      command: run.command,
      target: run.targets[0] ?? "",
      resume: true,
      snapshot_id: snapshotId,
      resume_run_name: run.run_name,
      options: {},
    }),
  });
}

export function stopTask(taskId: string): Promise<{ status: string; task_id: string }> {
  return requestJson(`/api/tasks/${taskId}/stop`, {
    method: "POST",
  });
}

export function openTaskStream(
  taskId: string,
  onEvent: (event: TaskEvent) => void,
  handlers: { onOpen?: () => void; onError?: () => void } = {},
): EventSource {
  const source = new EventSource(`/api/tasks/${taskId}/stream`);
  source.onopen = () => handlers.onOpen?.();
  source.onerror = () => handlers.onError?.();
  const handler = (message: MessageEvent<string>) => {
    try {
      const parsed = JSON.parse(message.data) as TaskEvent;
      onEvent(parsed);
    } catch {
      // Ignore malformed events.
    }
  };

  for (const eventName of TASK_EVENT_NAMES) {
    source.addEventListener(eventName, handler as EventListener);
  }
  source.onmessage = handler;
  return source;
}
export function getIntegrationDeliveries(name?: string, limit = 50): Promise<IntegrationDeliveryLogView[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (name) params.set("name", name);
  return requestJson<IntegrationDeliveryLogView[]>(`/api/integrations/deliveries?${params.toString()}`);
}

export function retryIntegrationDelivery(name: string): Promise<IntegrationDeliveryResult> {
  return requestJson<IntegrationDeliveryResult>(`/api/integrations/${encodeURIComponent(name)}/retry`, {
    method: "POST",
  });
}

export function getSchedules(): Promise<ScheduleView[]> {
  return requestJson<ScheduleView[]>("/api/schedules");
}

export function saveSchedule(payload: ScheduleUpsertRequest): Promise<ScheduleView> {
  return requestJson<ScheduleView>("/api/schedules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteSchedule(name: string): Promise<{ status: string; name: string }> {
  return requestJson(`/api/schedules/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export function runDueSchedules(): Promise<ScheduleView[]> {
  return requestJson<ScheduleView[]>("/api/schedules/run-due", { method: "POST" });
}
