import { useQuery } from "@tanstack/react-query";
import { getConfig, getConstraintAudit, getFindings, getIntegrationDeliveries, getIntegrations, getMcpDiagnostics, getPlugins, getProjects, getProviders, getReportContent, getReports, getRunDetail, getRuns, getSchedules, getTarget, getTargetDiff, getTargetPreview, getTargetSnapshots, getTargets, getTasks } from "../api/web";

export function useConfigQuery() {
  return useQuery({
    queryKey: ["config"],
    queryFn: getConfig,
    staleTime: 30_000,
  });
}

export function useProvidersQuery() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: getProviders,
    staleTime: 300_000,
  });
}

export function useMcpDiagnosticsQuery() {
  return useQuery({
    queryKey: ["mcp-diagnostics"],
    queryFn: getMcpDiagnostics,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

export function useConstraintAuditQuery() {
  return useQuery({
    queryKey: ["constraint-audit"],
    queryFn: getConstraintAudit,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

export function useTargetsQuery() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: getTargets,
    staleTime: 15_000,
  });
}

export function useTasksQuery() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: getTasks,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}

export function useTargetQuery(target: string | null) {
  return useQuery({
    queryKey: ["target", target],
    queryFn: () => getTarget(target as string),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useTargetSnapshotsQuery(target: string | null) {
  return useQuery({
    queryKey: ["target-snapshots", target],
    queryFn: () => getTargetSnapshots(target as string),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useTargetPreviewQuery(target: string | null) {
  return useQuery({
    queryKey: ["target-preview", target],
    queryFn: () => getTargetPreview(target as string),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useTargetDiffQuery(target: string | null, fromSnapshotId: string | null, toSnapshotId?: string | null) {
  return useQuery({
    queryKey: ["target-diff", target, fromSnapshotId, toSnapshotId ?? null],
    queryFn: () => getTargetDiff(target as string, fromSnapshotId as string, toSnapshotId ?? undefined),
    enabled: Boolean(target && fromSnapshotId),
    staleTime: 10_000,
  });
}

export function useReportsQuery() {
  return useQuery({
    queryKey: ["reports"],
    queryFn: getReports,
    staleTime: 30_000,
  });
}

export function useReportContentQuery(path: string | null) {
  return useQuery({
    queryKey: ["report-content", path],
    queryFn: () => getReportContent(path as string),
    enabled: Boolean(path),
    staleTime: 30_000,
  });
}

export function useRunsQuery() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: getRuns,
    staleTime: 15_000,
  });
}

export function useRunDetailQuery(runName: string | null) {
  return useQuery({
    queryKey: ["run", runName],
    queryFn: () => getRunDetail(runName as string),
    enabled: Boolean(runName),
    staleTime: 10_000,
  });
}

export function useFindingsQuery(target: string | null) {
  return useQuery({
    queryKey: ["findings", target],
    queryFn: () => getFindings(target as string),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useProjectsQuery() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
    staleTime: 30_000,
  });
}

export function useIntegrationsQuery() {
  return useQuery({
    queryKey: ["integrations"],
    queryFn: getIntegrations,
    staleTime: 15_000,
  });
}

export function usePluginsQuery() {
  return useQuery({
    queryKey: ["plugins"],
    queryFn: getPlugins,
    staleTime: 60_000,
  });
}

export function useIntegrationDeliveriesQuery(name?: string) {
  return useQuery({
    queryKey: ["integration-deliveries", name ?? "all"],
    queryFn: () => getIntegrationDeliveries(name, 50),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}

export function useSchedulesQuery() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: getSchedules,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
