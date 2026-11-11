import { useRunDetailQuery } from "../hooks/queries";
import { useDialogFocus } from "../hooks/useDialogFocus";
import { useT } from "../i18n";
import type { RunDetail } from "../types/api";

interface RunDetailDialogProps {
  open: boolean;
  runName: string | null;
  onClose: () => void;
  onResume?: (run: RunDetail) => Promise<void> | void;
}

function asText(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function findingItems(raw: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(raw)) return raw.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
  if (raw && typeof raw === "object" && Array.isArray((raw as Record<string, unknown>).findings)) {
    return ((raw as Record<string, unknown>).findings as unknown[]).filter(
      (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
    );
  }
  return [];
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}

export function RunDetailDialog({ open, runName, onClose, onResume }: RunDetailDialogProps) {
  const { t } = useT();
  const dialogRef = useDialogFocus<HTMLElement>(open && Boolean(runName), onClose);
  const query = useRunDetailQuery(open ? runName : null);

  if (!open || !runName) return null;
  const run = query.data;
  const evidence = run ? findingItems(run.findings) : [];
  const canResume = Boolean(
    run &&
      onResume &&
      run.targets.length &&
      (run.status === "failed" ||
        run.status === "interrupted" ||
        typeof run.resume?.last_snapshot_id === "string"),
  );

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        ref={dialogRef}
        className="report-dialog run-detail-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="report-dialog-header">
          <div>
            <span className="dialog-kicker">{t("dialog.run_detail")}</span>
            <h3 id="run-detail-title">{runName}</h3>
            {run && (
              <>
                <p>
                  {run.command} · {run.status} · {t("run.exit_code", { code: String(run.exit_code) })}
                </p>
                {run.message && <p className="run-message">{run.message}</p>}
              </>
            )}
          </div>
          <div className="report-dialog-actions">
            {canResume && (
              <button className="secondary-btn" type="button" onClick={() => run && void onResume?.(run)}>
                {t("run.resume")}
              </button>
            )}
            <button className="secondary-btn" type="button" onClick={onClose}>
              {t("dialog.close")}
            </button>
          </div>
        </header>

        {query.isLoading && <div className="empty-state">{t("dialog.loading_preview")}</div>}
        {query.isError && <div className="error-box">{String(query.error)}</div>}
        {run && (
          <div className="run-detail-grid">
            <section>
              <h4>{t("run.timeline")}</h4>
              <div className="list list-scroll run-timeline">
                {run.events.length ? (
                  run.events.map((event, index) => (
                    <article key={`${event.timestamp}-${index}`} className="list-item">
                      <strong>{event.kind || t("run.event")}</strong>
                      <span className="muted-inline">{event.timestamp}</span>
                      <code className="run-event-payload">
                        {JSON.stringify(event.payload).slice(0, 220)}
                      </code>
                    </article>
                  ))
                ) : (
                  <div className="empty-state">{t("run.no_events")}</div>
                )}
              </div>
            </section>
            <section>
              <h4>{t("run.artifacts")}</h4>
              <div className="list run-artifacts">
                {Object.entries(run.artifacts).map(([key, value]) => (
                  <div key={key} className="list-item">
                    <strong>{key}</strong>
                    <code>{value}</code>
                  </div>
                ))}
              </div>
              <h4>{t("run.reports")}</h4>
              <div className="list run-artifacts">
                {run.reports.length ? (
                  run.reports.map((report) => (
                    <div key={report} className="list-item">
                      <code>{report}</code>
                    </div>
                  ))
                ) : (
                  <div className="empty-state">{t("run.no_reports")}</div>
                )}
              </div>
            </section>
            <section className="run-detail-wide">
              <h4>{t("run.phases")}</h4>
              <div className="list run-phases">
                {run.phases.length ? (
                  run.phases.map((phase) => (
                    <div key={phase.name} className="list-item">
                      <strong>{phase.name}</strong>
                      <span className="muted-inline">
                        {formatDuration(phase.duration_seconds)} · {t("run.events_count", { count: String(phase.event_count) })}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="empty-state">{t("run.no_phases")}</div>
                )}
              </div>
            </section>
            <section className="run-detail-wide">
              <h4>{t("run.evidence")}</h4>
              <div className="list list-scroll run-evidence">
                {evidence.length ? (
                  evidence.map((item, index) => (
                    <article key={`${asText(item.finding_id, "")}-${index}`} className="list-item">
                      <strong>{asText(item.title, t("run.event"))}</strong>
                      <span className="muted-inline">
                        {asText(item.severity, t("risk.uncategorized"))} · {asText(item.lifecycle_status, t("run.event"))}
                      </span>
                      {asText(item.evidence) && <code className="run-event-payload">{asText(item.evidence).slice(0, 320)}</code>}
                    </article>
                  ))
                ) : (
                  <div className="empty-state">{t("run.no_evidence")}</div>
                )}
              </div>
            </section>
          </div>
        )}
      </section>
    </div>
  );
}