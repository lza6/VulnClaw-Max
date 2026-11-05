import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { deleteIntegration, retryIntegrationDelivery, saveIntegration, testIntegration } from "../api/web";
import { useIntegrationDeliveriesQuery, useIntegrationsQuery } from "../hooks/queries";
import { useT, type TFunction } from "../i18n";
import type { IntegrationDeliveryLogView, IntegrationEvent, IntegrationKind } from "../types/api";
import { ConfirmDialog } from "./ConfirmDialog";

const KINDS: IntegrationKind[] = ["webhook", "jira", "defectdojo"];
const EVENTS: IntegrationEvent[] = ["run.completed", "run.failed"];

interface Draft {
  name: string;
  kind: IntegrationKind;
  url: string;
  token: string;
  project_key: string;
  enabled: boolean;
  events: IntegrationEvent[];
  editing: boolean;
  tokenConfigured: boolean;
}

function emptyDraft(): Draft {
  return {
    name: "",
    kind: "webhook",
    url: "",
    token: "",
    project_key: "",
    enabled: true,
    events: [...EVENTS],
    editing: true,
    tokenConfigured: false,
  };
}

export function IntegrationsPanel() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const integrationsQuery = useIntegrationsQuery();
  const deliveriesQuery = useIntegrationDeliveriesQuery();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const integrations = integrationsQuery.data ?? [];
  const deliveries = deliveriesQuery.data ?? [];

  useEffect(() => {
    if (integrationsQuery.error) {
      setError(integrationsQuery.error instanceof Error ? integrationsQuery.error.message : String(integrationsQuery.error));
    }
  }, [integrationsQuery.error]);

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["integrations"] });
    void queryClient.invalidateQueries({ queryKey: ["integration-deliveries"] });
  }

  function startCreate() {
    setStatus(null);
    setError(null);
    setDraft(emptyDraft());
  }

  function startEdit(name: string) {
    const item = integrations.find((entry) => entry.name === name);
    if (!item) return;
    setStatus(null);
    setError(null);
    setDraft({
      name: item.name,
      kind: item.kind,
      url: item.url,
      token: "",
      project_key: item.project_key,
      enabled: item.enabled,
      events: item.events.length ? [...item.events] : [...EVENTS],
      editing: false,
      tokenConfigured: item.token_configured,
    });
  }

  function toggleEvent(event: IntegrationEvent) {
    if (!draft) return;
    const events = draft.events.includes(event)
      ? draft.events.filter((item) => item !== event)
      : [...draft.events, event];
    setDraft({ ...draft, events });
  }

  async function handleSave() {
    if (!draft) return;
    if (!draft.name.trim() || !draft.url.trim()) {
      setError(t("integrations.required_fields"));
      return;
    }
    if (draft.editing && integrations.some((item) => item.name === draft.name.trim())) {
      setError(t("integrations.name_taken", { name: draft.name.trim() }));
      return;
    }
    if (draft.kind === "defectdojo" && draft.project_key.trim() && !/^\d+$/.test(draft.project_key.trim())) {
      setError(t("integrations.defectdojo_product_numeric"));
      return;
    }
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      await saveIntegration({
        name: draft.name.trim(),
        kind: draft.kind,
        url: draft.url.trim(),
        token: draft.token,
        project_key: draft.project_key.trim(),
        enabled: draft.enabled,
        events: draft.events,
      });
      refresh();
      setStatus(t("integrations.saved", { name: draft.name.trim() }));
      setDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleTest(name: string) {
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      const result = await testIntegration(name);
      if (result.ok) {
        setStatus(t("integrations.test_ok", { name, attempts: String(result.attempts) }));
      } else {
        setError(
          t("integrations.test_failed", {
            name,
            detail: result.status_code ? `HTTP ${result.status_code}` : result.error || t("integrations.test_failed_unknown"),
          }),
        );
      }
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("integrations.test_failed_unknown"));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry(name: string) {
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      const result = await retryIntegrationDelivery(name);
      if (result.ok) {
        setStatus(t("integrations.retry_ok", { name, attempts: String(result.attempts) }));
      } else {
        setError(
          t("integrations.retry_failed", {
            name,
            detail: result.status_code ? `HTTP ${result.status_code}` : result.error || t("integrations.test_failed_unknown"),
          }),
        );
      }
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("integrations.test_failed_unknown"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(name: string) {
    try {
      setBusy(true);
      setError(null);
      setStatus(null);
      await deleteIntegration(name);
      refresh();
      if (draft?.name === name) setDraft(null);
      setStatus(t("integrations.deleted", { name }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="integrations-panel">
      <div className="inline-panel field-wide">
        <strong>{t("integrations.notify_note_title")}</strong>
        <p className="inline-note">{t("integrations.notify_note")}</p>
      </div>

      <div className="list list-scroll integrations-list">
        {integrations.map((item) => {
          const last = deliveries.find((entry) => entry.name === item.name);
          return (
            <div key={item.name} className="list-item integration-item">
              <div className="integration-item-head">
                <strong>{item.name}</strong>
                <span className={`badge badge-${item.kind}`}>{item.kind}</span>
                <span className={item.enabled ? "status-ok" : "status-muted"}>
                  {item.enabled ? t("integrations.enabled") : t("integrations.disabled")}
                </span>
              </div>
              <span className="muted-inline">{item.url}</span>
              <span className="muted-inline">
                {item.token_configured ? t("integrations.token_set") : t("integrations.token_missing")}
                {` · ${formatEvents(item.events, t)}`}
                {item.project_key ? ` · ${t("integrations.project_key")}: ${item.project_key}` : ""}
              </span>
              <span className={last ? (last.ok ? "status-ok" : "danger-inline") : "status-muted"}>
                {last
                  ? `${t(last.ok ? "integrations.delivery_ok" : "integrations.delivery_failed")} · ${formatDeliveryLine(last, t)}`
                  : t("integrations.never_delivered")}
              </span>
              <div className="integration-item-actions">
                <button className="text-btn inline-text-btn" disabled={busy} onClick={() => void handleTest(item.name)} type="button">
                  {t("integrations.test")}
                </button>
                {last && !last.ok && last.retryable && (
                  <button className="text-btn inline-text-btn" disabled={busy} onClick={() => void handleRetry(item.name)} type="button">
                    {t("integrations.retry")}
                  </button>
                )}
                <button className="text-btn inline-text-btn" onClick={() => startEdit(item.name)} type="button">
                  {t("integrations.edit")}
                </button>
                <button className="text-btn inline-text-btn danger-text-btn" disabled={busy} onClick={() => setPendingDelete(item.name)} type="button">
                  {t("integrations.delete")}
                </button>
              </div>
            </div>
          );
        })}
        {!integrations.length && <div className="empty-state">{t("integrations.empty")}</div>}
      </div>

      {!draft && (
        <div className="button-row">
          <button className="secondary-btn" onClick={startCreate} type="button">
            {t("integrations.add")}
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
              placeholder="slack-alerts"
            />
            <small>{t("integrations.name_hint")}</small>
          </label>
          <label className="field">
            <span>{t("integrations.kind")}</span>
            <select
              value={draft.kind}
              disabled={!draft.editing}
              onChange={(event) => setDraft({ ...draft, kind: event.target.value as IntegrationKind })}
            >
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`integrations.kind_${kind}`)}
                </option>
              ))}
            </select>
            <small>{t("integrations.kind_hint")}</small>
          </label>
          <label className="field field-wide">
            <span>{t("integrations.url")}</span>
            <input
              value={draft.url}
              onChange={(event) => setDraft({ ...draft, url: event.target.value })}
              placeholder={draft.kind === "webhook" ? "https://hooks.example.com/vulnclaw" : "https://jira.example.com"}
            />
            <small>{draft.kind === "webhook" ? t("integrations.url_hint_webhook") : t("integrations.url_hint_platform")}</small>
          </label>
          <label className="field">
            <span>{t("integrations.token")}</span>
            <input
              type="password"
              value={draft.token}
              onChange={(event) => setDraft({ ...draft, token: event.target.value })}
              placeholder={draft.tokenConfigured ? "••••••" : ""}
            />
            <small>{draft.tokenConfigured ? t("integrations.token_keep") : t("integrations.token_hint")}</small>
          </label>
          <label className="field">
            <span>{t("integrations.project_key")}</span>
            <input
              value={draft.project_key}
              onChange={(event) => setDraft({ ...draft, project_key: event.target.value })}
              placeholder={draft.kind === "defectdojo" ? "1" : "SEC"}
            />
            <small>{t(`integrations.project_key_hint_${draft.kind}`)}</small>
          </label>
          <label className="check-row">
            <input
              checked={draft.enabled}
              onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
              type="checkbox"
            />
            <span>{t("integrations.enabled_label")}</span>
          </label>
          <div className="field field-wide">
            <span>{t("integrations.events")}</span>
            <div className="check-row-group">
              {EVENTS.map((event) => (
                <label key={event} className="check-row">
                  <input
                    checked={draft.events.includes(event)}
                    onChange={() => toggleEvent(event)}
                    type="checkbox"
                  />
                  <span>{t(`integrations.event_${event.replace(".", "_")}`)}</span>
                </label>
              ))}
            </div>
            <small>{t(`integrations.events_hint_${draft.kind}`)}</small>
          </div>
          <div className="button-row field-wide">
            <button className="primary-btn" disabled={busy} onClick={() => void handleSave()} type="button">
              {busy ? t("settings.saving") : t("integrations.save")}
            </button>
            <button className="secondary-btn" onClick={() => setDraft(null)} type="button">
              {t("integrations.cancel")}
            </button>
          </div>
        </div>
      )}

      {status && <div className="success-box">{status}</div>}
      {error && <div className="error-box">{error}</div>}

      <div className="delivery-history">
        <strong>{t("integrations.history_title")}</strong>
        {deliveries.length ? (
          <div className="list list-scroll delivery-history-list">
            {deliveries.slice(0, 15).map((entry, index) => (
              <div key={`${entry.at}-${entry.name}-${index}`} className="list-item delivery-history-item">
                <span className={entry.ok ? "status-ok" : "danger-inline"}>
                  {entry.ok ? t("integrations.delivery_ok") : t("integrations.delivery_failed")} · {entry.name}
                </span>
                <span className="muted-inline">{formatDeliveryLine(entry, t)}</span>
                {entry.error && <span className="danger-inline">{entry.error}</span>}
              </div>
            ))}
          </div>
        ) : (
          <p className="inline-note">{t("integrations.history_empty")}</p>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title={t("integrations.confirm_delete_title")}
        copy={t("integrations.confirm_delete_copy", { name: pendingDelete ?? "" })}
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

function formatEvents(events: IntegrationEvent[], t: TFunction): string {
  if (!events.length) return t("integrations.events_none");
  return events.map((event) => t(`integrations.event_${event.replace(".", "_")}`)).join(", ");
}

function formatDeliveryLine(entry: IntegrationDeliveryLogView, t: TFunction): string {
  const when = entry.at ? new Date(entry.at).toLocaleString() : t("reports.unknown_date");
  const scope =
    entry.kind === "findings"
      ? t("integrations.delivery_scope_findings", { count: String(entry.items) })
      : t("integrations.delivery_scope_event", { event: entry.event || entry.kind });
  const status = entry.status_code ? `HTTP ${entry.status_code}` : entry.ok ? t("integrations.delivery_ok") : "";
  return [when, scope, status].filter(Boolean).join(" · ");
}
