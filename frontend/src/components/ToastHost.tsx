import { AnimatePresence, m } from "motion/react";
import { useT } from "../i18n";
import { DURATION } from "../motion/tokens";
import { useMotionPrefs } from "../motion/useMotionPrefs";

export type ToastTone = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  copy?: string;
  actionLabel?: string;
  onAction?: () => void;
}

interface ToastHostProps {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}

export function ToastHost({ toasts, onDismiss }: ToastHostProps) {
  const { t } = useT();
  const { reduce, seconds, ease } = useMotionPrefs();

  return (
    <div className="toast-host" aria-live="polite" aria-relevant="additions removals">
      <AnimatePresence initial={false}>
        {toasts.map((toast) => (
        <m.article
          key={toast.id}
          className={`toast toast-${toast.tone}`}
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? undefined : { opacity: 0, y: 8 }}
          transition={{ duration: seconds(DURATION.fast), ease }}
        >
          <div>
            <strong>{toast.title}</strong>
            {toast.copy && <p>{toast.copy}</p>}
            {toast.actionLabel && toast.onAction && (
              <button
                type="button"
                className="toast-action-btn"
                onClick={() => {
                  toast.onAction?.();
                  onDismiss(toast.id);
                }}
              >
                {toast.actionLabel}
              </button>
            )}
          </div>
          <button type="button" className="toast-close-btn" aria-label={t("dialog.close")} onClick={() => onDismiss(toast.id)}>
            x
          </button>
        </m.article>
        ))}
      </AnimatePresence>
    </div>
  );
}
