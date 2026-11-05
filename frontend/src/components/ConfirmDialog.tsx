import { useT } from "../i18n";
import { useDialogFocus } from "../hooks/useDialogFocus";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  copy: string;
  tone?: "primary" | "danger";
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, copy, tone = "primary", confirmLabel, onConfirm, onCancel }: ConfirmDialogProps) {
  const { t } = useT();
  const dialogRef = useDialogFocus<HTMLElement>(open, onCancel);

  if (!open) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onCancel}>
      <section ref={dialogRef} className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-copy" onMouseDown={(event) => event.stopPropagation()}>
        <span className="dialog-kicker">{t("dialog.confirmation_required")}</span>
        <h3 id="confirm-title">{title}</h3>
        <p id="confirm-copy" className="confirm-copy">{copy}</p>
        <div className="button-row compact-row">
          <button type="button" className="secondary-btn" onClick={onCancel}>
            {t("dialog.cancel")}
          </button>
          <button type="button" className={tone === "danger" ? "danger-btn" : "primary-btn"} onClick={onConfirm}>
            {confirmLabel ?? t("dialog.confirm")}
          </button>
        </div>
      </section>
    </div>
  );
}
