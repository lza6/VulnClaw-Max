import { useMemo, useState } from "react";
import { SectionCard } from "../components/SectionCard";
import { usePluginsQuery } from "../hooks/queries";
import { useT } from "../i18n";
import type { PluginView } from "../types/api";

const STAGES = ["recon", "discovery", "verification", "exploitation", "post_exploitation", "reporting"];

export function PluginsPage() {
  const { t } = useT();
  const pluginsQuery = usePluginsQuery();
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState<string>("all");
  const [origin, setOrigin] = useState<"all" | "builtin" | "external">("all");

  const plugins = pluginsQuery.data?.plugins ?? [];
  const loadErrors = pluginsQuery.data?.errors ?? [];

  const visible = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return plugins.filter((plugin) => {
      if (stage !== "all" && !plugin.stages.includes(stage)) return false;
      if (origin !== "all" && plugin.origin !== origin) return false;
      if (!keyword) return true;
      const haystack = `${plugin.plugin_id} ${plugin.name} ${plugin.description} ${plugin.tags.join(" ")}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [plugins, search, stage, origin]);

  return (
    <section className="plugins-page">
      <SectionCard
        title={t("plugins.title")}
        copy={t("plugins.copy")}
        aside={
          <span className="status-badge">
            {t("plugins.count", { count: String(visible.length), total: String(plugins.length) })}
          </span>
        }
      >
        <div className="plugin-filter-grid">
          <label className="field">
            <span>{t("plugins.search")}</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("plugins.search_placeholder")}
            />
          </label>
          <label className="field">
            <span>{t("plugins.stage_filter")}</span>
            <select value={stage} onChange={(event) => setStage(event.target.value)}>
              <option value="all">{t("plugins.all_stages")}</option>
              {STAGES.map((value) => (
                <option key={value} value={value}>
                  {t(`plugins.stage_${value}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("plugins.origin_filter")}</span>
            <select value={origin} onChange={(event) => setOrigin(event.target.value as "all" | "builtin" | "external")}>
              <option value="all">{t("plugins.all_origins")}</option>
              <option value="builtin">{t("plugins.origin_builtin")}</option>
              <option value="external">{t("plugins.origin_external")}</option>
            </select>
          </label>
        </div>

        <div className="inline-panel field-wide">
          <strong>{t("plugins.cli_hint_title")}</strong>
          <p className="inline-note">{t("plugins.cli_hint")}</p>
        </div>

        {pluginsQuery.isLoading && <div className="empty-state">{t("plugins.loading")}</div>}
        {pluginsQuery.error && (
          <div className="error-box">
            {pluginsQuery.error instanceof Error ? pluginsQuery.error.message : t("error.save_failed")}
          </div>
        )}

        <div className="plugin-grid">
          {visible.map((plugin) => (
            <PluginCard key={plugin.plugin_id} plugin={plugin} />
          ))}
        </div>
        {!pluginsQuery.isLoading && !visible.length && (
          <div className="empty-state">{t("plugins.empty")}</div>
        )}
      </SectionCard>

      {Boolean(loadErrors.length) && (
        <SectionCard title={t("plugins.load_errors")} copy={t("plugins.load_errors_copy")}>
          <div className="list list-scroll">
            {loadErrors.map((item) => (
              <div key={`${item.entry_point}-${item.error}`} className="list-item">
                <strong>{item.entry_point}</strong>
                <span className="danger-inline">{item.error}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </section>
  );
}

function PluginCard({ plugin }: { plugin: PluginView }) {
  const { t } = useT();
  return (
    <article className="plugin-card">
      <div className="plugin-card-head">
        <strong>{plugin.name}</strong>
        <span className="badge">{plugin.origin === "builtin" ? t("plugins.origin_builtin") : t("plugins.origin_external")}</span>
        <span className="status-muted">v{plugin.version}</span>
        {plugin.destructive && <span className="plugin-tag plugin-tag-danger">{t("plugins.destructive")}</span>}
      </div>
      <code>{plugin.plugin_id}</code>
      <p className="muted-inline">{plugin.description || t("plugins.no_description")}</p>
      <div className="plugin-meta">
        <span className="plugin-tag">{t("plugins.risk_label")}: {plugin.default_risk}</span>
        {plugin.stages.map((value) => (
          <span key={value} className="plugin-tag">
            {t(`plugins.stage_${value}`, undefined, value)}
          </span>
        ))}
        {plugin.permissions.map((value) => (
          <span key={value} className="plugin-tag">
            {value}
          </span>
        ))}
        {plugin.requires_target && <span className="plugin-tag">{t("plugins.requires_target")}</span>}
        {!plugin.enabled && <span className="plugin-tag plugin-tag-danger">{t("plugins.disabled")}</span>}
      </div>
    </article>
  );
}
