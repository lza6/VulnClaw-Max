import { AnimatePresence, m } from "motion/react";
import { DURATION } from "../motion/tokens";
import { useMotionPrefs } from "../motion/useMotionPrefs";
import { useT } from "../i18n";
import { useDialogFocus } from "../hooks/useDialogFocus";

interface ReportPreviewDialogProps {
  open: boolean;
  title: string;
  path?: string;
  content?: string;
  kind?: string;
  loading: boolean;
  onDownload?: () => void;
  onClose: () => void;
}

interface ReportPreviewProps {
  content?: string;
  kind?: string;
  loading: boolean;
  expanded?: boolean;
}

export function ReportPreviewDialog({ open, title, path, content, kind, loading, onDownload, onClose }: ReportPreviewDialogProps) {
  const { t } = useT();
  const { reduce, seconds, ease, exitEase } = useMotionPrefs();
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);

  return (
    <AnimatePresence>
      {open && (
    <m.div
      className="dialog-backdrop"
      role="presentation"
      initial={reduce ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={reduce ? undefined : { opacity: 0 }}
      transition={{ duration: seconds(DURATION.fast), ease }}
      onMouseDown={onClose}
    >
      <m.section
        ref={dialogRef}
        className="report-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-preview-title"
        initial={reduce ? false : { opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={reduce ? undefined : { opacity: 0, scale: 0.98 }}
        transition={{ duration: seconds(DURATION.fast), ease: exitEase }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="report-dialog-header">
          <div>
            <span className="dialog-kicker">{t("dialog.report_preview")}</span>
            <h3 id="report-preview-title">{title}</h3>
            {path && <p>{path}</p>}
          </div>
          <div className="report-dialog-actions">
            <button className="secondary-btn" disabled={(!content && kind !== "pdf") || !onDownload} type="button" onClick={onDownload}>
              {t("dialog.download")}
            </button>
            <button className="secondary-btn" type="button" onClick={onClose}>
              {t("dialog.close")}
            </button>
          </div>
        </header>
        <ReportPreview content={content} kind={kind} loading={loading} expanded />
      </m.section>
    </m.div>
      )}
    </AnimatePresence>
  );
}

export function ReportPreview({ content, kind, loading, expanded = false }: ReportPreviewProps) {
  const { t } = useT();
  return (
    <div className={`report-preview ${expanded ? "report-preview-expanded" : ""}`}>
      {kind === "pdf" ? (
        <div className="empty-state">{t("reports.pdf_download_only")}</div>
      ) : content ? (
        kind === "html" ? (
          <iframe className="report-frame" sandbox="" srcDoc={content} title="HTML report preview" />
        ) : (
          <pre>{content}</pre>
        )
      ) : loading ? (
        <div className="empty-state">{t("dialog.loading_preview")}</div>
      ) : (
        <div className="empty-state">{t("dialog.select_report_preview")}</div>
      )}
    </div>
  );
}
