/**
 * Canonical task event names. Keep in sync with
 * `vulnclaw/web/event_names.py`; a Python test compares both lists.
 */
export const TASK_EVENT_NAMES = [
  "task_created",
  "task_queued",
  "task_restoring",
  "task_started",
  "task_state_changed",
  "legacy_import",
  "round_output",
  "cycle_completed",
  "task_completed",
  "task_failed",
  "task_stopped",
  "task_interrupted",
  "event_gap",
] as const;
