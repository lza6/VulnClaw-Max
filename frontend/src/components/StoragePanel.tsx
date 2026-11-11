import { useEffect, useState } from "react";
import { getStorage, runGc } from "../api/web";
import { useT } from "../i18n";
import type { StorageUsage } from "../types/api";
import { SectionCard } from "./SectionCard";

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function StoragePanel() {
  const { t } = useT();
  const [usage, setUsage] = useState<StorageUsage | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setUsage(await getStorage());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleGc(dryRun: boolean) {
    try {
      setBusy(true);
      setError(null);
      const result = await runGc({ older_than: 30, keep_last: 50, dry_run: dryRun });
      setMessage(
        t("settings.gc_result", {
          count: String(result.removed),
          bytes: formatBytes(result.freed_bytes),
        }),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const rows = usage
    ? [
        ["sessions", usage.sessions_bytes],
        ["runs", usage.runs_bytes],
        ["targets", usage.targets_bytes],
        ["projects", usage.projects_bytes],
        ["web events", usage.web_events_bytes],
        ["web tasks", usage.web_tasks_bytes],
      ]
    : [];

  return (
    <SectionCard title={t("settings.storage")} copy={t("settings.storage_copy")}>
      <div className="storage-usage">
        <div className="stat-grid">
          {rows.map(([label, value]) => (
            <article key={String(label)} className="stat">
              <span className="stat-label">{String(label)}</span>
              <strong>{formatBytes(Number(value))}</strong>
            </article>
          ))}
          {usage && (
            <article className="stat">
              <span className="stat-label">{t("settings.storage_total")}</span>
              <strong>{formatBytes(usage.total_bytes)}</strong>
            </article>
          )}
        </div>
        <div className="button-row">
          <button className="secondary-btn" type="button" disabled={busy} onClick={() => void handleGc(true)}>
            {t("settings.gc_dry_run")}
          </button>
          <button className="secondary-btn danger-btn" type="button" disabled={busy} onClick={() => void handleGc(false)}>
            {t("settings.gc_run")}
          </button>
        </div>
        {message && <div className="success-box">{message}</div>}
        {error && <div className="error-box">{error}</div>}
      </div>
    </SectionCard>
  );
}
