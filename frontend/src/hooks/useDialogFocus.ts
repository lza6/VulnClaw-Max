import { useEffect, useRef } from "react";

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function useDialogFocus<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T | null>(null);
  const previous = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    previous.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const container = ref.current;
    const focusables = container ? Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
    (focusables[0] ?? container)?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previous.current?.focus?.();
    };
  }, [open, onClose]);

  return ref;
}
