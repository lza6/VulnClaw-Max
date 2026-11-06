import { m } from "motion/react";
import { DURATION } from "../motion/tokens";
import { useMotionPrefs } from "../motion/useMotionPrefs";

interface StatusDotProps {
  tone?: "idle" | "ok" | "warn" | "danger" | "running";
  label: string;
}

export function StatusDot({ tone = "idle", label }: StatusDotProps) {
  const { reduce, seconds, ease } = useMotionPrefs();
  return (
    <span className={`status-dot status-dot-${tone}`}>
      <m.span
        key={`${tone}:${label}`}
        aria-hidden="true"
        initial={reduce ? false : { scale: 0.82 }}
        animate={{ scale: 1 }}
        transition={{ duration: seconds(DURATION.fast), ease }}
      />
      {label}
    </span>
  );
}
