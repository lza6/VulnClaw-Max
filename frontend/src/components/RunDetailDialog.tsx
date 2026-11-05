import { useRunDetailQuery } from "../hooks/queries";
import { useDialogFocus } from "../hooks/useDialogFocus";
import { useT } from "../i18n";

interface RunDetailDialogProps {
  open: boolean;
  runName: string | null;
  onClose: () => void;
}

export function RunDetailDialog({ open, runName, onClose }: RunDetailDialogProps) {
  const { t } = useT();
  const dialogRef = useDialogFocus<HTMLElement>(open && Boolean(runName), onClose);
  const query = useRunDetailQuery(open ? runName : null);

  if (!open || !runName) return null;
  const run = query.data;

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
          </div>
        )}
      </section>
    </div>
  );
}