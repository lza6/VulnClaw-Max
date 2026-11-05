import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { deleteSchedule, runDueSchedules, saveSchedule } from "../api/web";
import { useSchedulesQuery } from "../hooks/queries";
import { useT } from "../i18n";
import type { ScheduleCommand, ScheduleView } from "../types/api";
import { formatTaskCommand } from "../utils/taskLabels";
import { ConfirmDialog } from "./ConfirmDialog";

const COMMANDS: ScheduleCommand[] = ["recon", "scan", "exploit", "persistent", "run", "codescan"];

interface Draft {
  name: string;
  target: string;
  command: ScheduleCommand;
  minutes: string;
  enabled: boolean;
  options: string;
  editing: boolean;
}

function emptyDraft(): Draft {
  return { name: "", target: "", command: "recon", minutes: "60", enabled: true, options: "", editing: true };
}

export function SchedulesPanel() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const schedulesQuery = useSchedulesQuery();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const schedules = useMemo(() => schedulesQuery.data ?? [], [schedulesQuery.data]);

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["schedules"] });
  }

  function startCreate() {
    setStatus(null);
    setError(null);
    setDraft(emptyDraft());
  }

  function startEdit(job: ScheduleView) {
    setStatus(null);
    setError(null);
    setDraft({
      name: job.name,
      target: job.target,
      command: job.command,
      minutes: String(Math.round(job.interval_seconds / 60)),
      enabled: job.enabled,
      options: Object.keys(job.options ?? {}).length ? JSON.stringify(job.options) : "",
      editing: false,
    });
  }

  function parseDraft(current: Draft): { intervalSeconds: number; options: Record<string, unknown> } | null {
    const minutes = Number(current.minutes);
    if (!Number.isFinite(minutes) || minutes < 1) {
      setError(t("schedules.interval_invalid"));
      return null;
    }
    let options: Record<string, unknown> = {};
    if (current.options.trim()) {
      try {
        const parsed = JSON.parse(current.options) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          setError(t("schedules.options_invalid"));
          return null;
        }
        options = parsed as Record<string, unknown>;
      } catch {
        setError(t("schedules.options_invalid"));
        return null;
      }
    }
    return { intervalSeconds: Math.round(minutes * 60), options };
  }

  async function persist(current: Draft, overrides: Partial<Draft> = {}) {
    const merged = { ...current, ...overrides };
    if (!merged.name.trim() || !merged.target.trim()) {
      setError(t("schedules.required_fields"));
      return false;
    }
    const parsed = parseDraft(merged);
    if (!parsed) return false;
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      await saveSchedule({
        name: merged.name.trim(),
        target: merged.target.trim(),
        command: merged.command,
        interval_seconds: parsed.intervalSeconds,
        enabled: merged.enabled,
        options: parsed.options,
      });
      refresh();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.save_failed"));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    if (!draft) return;
    if (draft.editing && schedules.some((job) => job.name === draft.name.trim())) {
      setError(t("schedules.name_taken", { name: draft.name.trim() }));
      return;
    }
    if (await persist(draft)) {
      setStatus(t("schedules.saved", { name: draft.name.trim() }));
      setDraft(null);
    }
  }

  async function toggleEnabled(job: ScheduleView) {
    const ok = await persist(
      {
        name: job.name,
        target: job.target,
        command: job.command,
        minutes: String(Math.round(job.interval_seconds / 60)),
        enabled: job.enabled,
        options: Object.keys(job.options ?? {}).length ? JSON.stringify(job.options) : "",
        editing: false,
      },
      { enabled: !job.enabled },
    );
    if (ok) setStatus(t(job.enabled ? "schedules.disabled" : "schedules.enabled", { name: job.name }));
  }

  async function handleDelete(name: string) {
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      await deleteSchedule(name);
      refresh();
      if (draft?.name === name) setDraft(null);
      setStatus(t("schedules.deleted", { name }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleRunDue() {
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      const ran = await runDueSchedules();
      refresh();
      setStatus(
        ran.length
          ? t("schedules.ran_jobs", { count: String(ran.length), names: ran.map((job) => job.name).join(", ") })
          : t("schedules.nothing_due"),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="schedules-panel">
      <div className="inline-panel field-wide">
        <strong>{t("schedules.note_title")}</strong>
        <p className="inline-note">{t("schedules.note")}</p>
      </div>

      <div className="list list-scroll schedules-list">
        {schedules.map((job) => (
          <div key={job.name} className="list-item schedule-item">
            <div className="integration-item-head">
              <strong>{job.name}</strong>
              <span className="badge">{formatTaskCommand(job.command)}</span>
              <span className={job.enabled ? "status-ok" : "status-muted"}>
                {job.enabled ? t("schedules.state_enabled") : t("schedules.state_disabled")}
              </span>
            </div>
            <span className="muted-inline">
              {job.target} · {t("schedules.every_minutes", { minutes: String(Math.round(job.interval_seconds / 60)) })}
            </span>
            <span className="muted-inline">
              {t("schedules.next_run")}: {formatTimestamp(job.next_run, t)}
              {" · "}
              {t("schedules.last_run")}: {formatTimestamp(job.last_run, t)}
            </span>
            {Boolean(Object.keys(job.options ?? {}).length) && (
              <code className="schedule-options">{JSON.stringify(job.options)}</code>
            )}
            <div className="integration-item-actions">
              <button className="text-btn inline-text-btn" disabled={busy} onClick={() => void toggleEnabled(job)} type="button">
                {job.enabled ? t("schedules.disable") : t("schedules.enable")}
              </button>
              <button className="text-btn inline-text-btn" onClick={() => startEdit(job)} type="button">
                {t("integrations.edit")}
              </button>
              <button className="text-btn inline-text-btn danger-text-btn" disabled={busy} onClick={() => setPendingDelete(job.name)} type="button">
                {t("integrations.delete")}
              </button>
            </div>
          </div>
        ))}
        {!schedules.length && <div className="empty-state">{t("schedules.empty")}</div>}
      </div>

      {!draft && (
        <div className="button-row">
          <button className="secondary-btn" onClick={startCreate} type="button">
            {t("schedules.add")}
          </button>
          <button className="secondary-btn" disabled={busy || !schedules.length} onClick={() => void handleRunDue()} type="button">
            {t("schedules.run_due")}
          </button>
        </div>
      )}

      {draft && (
        <div className="form-grid integration-form">
          <label className="field">
            <span>{t("integrations.name")}</span>
            <input
              value={draft.name}
              disabled={!draft.editing}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              placeholder="nightly-recon"
            />
            <small>{t("schedules.name_hint")}</small>
          </label>
          <label className="field">
            <span>{t("schedules.command")}</span>
            <select
              value={draft.command}
              onChange={(event) => setDraft({ ...draft, command: event.target.value as ScheduleCommand })}
            >
              {COMMANDS.map((value) => (
                <option key={value} value={value}>
                  {formatTaskCommand(value)}
                </option>
              ))}
            </select>
          </label>
          <label className="field field-wide">
            <span>{t("schedules.target")}</span>
            <input
              value={draft.target}
              onChange={(event) => setDraft({ ...draft, target: event.target.value })}
              placeholder="example.com"
            />
          </label>
          <label className="field">
            <span>{t("schedules.interval")}</span>
            <input
              type="number"
              min="1"
              value={draft.minutes}
              onChange={(event) => setDraft({ ...draft, minutes: event.target.value })}
            />
            <small>{t("schedules.interval_hint")}</small>
          </label>
          <label className="check-row">
            <input
              checked={draft.enabled}
              onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
              type="checkbox"
            />
            <span>{t("schedules.enabled_label")}</span>
          </label>
          <label className="field field-wide">
            <span>{t("schedules.options")}</span>
            <textarea
              rows={3}
              value={draft.options}
              onChange={(event) => setDraft({ ...draft, options: event.target.value })}
              placeholder='{"ports": "80,443"}'
            />
            <small>{t("schedules.options_hint")}</small>
          </label>
          <div className="button-row field-wide">
            <button className="primary-btn" disabled={busy} onClick={() => void handleSave()} type="button">
              {busy ? t("settings.saving") : t("schedules.save")}
            </button>
            <button className="secondary-btn" onClick={() => setDraft(null)} type="button">
              {t("integrations.cancel")}
            </button>
          </div>
        </div>
      )}

      {status && <div className="success-box">{status}</div>}
      {error && <div className="error-box">{error}</div>}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={t("schedules.confirm_delete_title")}
        copy={t("schedules.confirm_delete_copy", { name: pendingDelete ?? "" })}
        tone="danger"
        confirmLabel={t("integrations.delete")}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const name = pendingDelete;
          setPendingDelete(null);
          if (name) void handleDelete(name);
        }}
      />
    </div>
  );
}

function formatTimestamp(value: number | null, t: (key: string) => string): string {
  if (!value) return t("schedules.never");
  return new Date(value * 1000).toLocaleString();
}
