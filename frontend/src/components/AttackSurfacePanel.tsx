import { lazy, Suspense, useState } from "react";
import { SectionCard } from "./SectionCard";
import { useT } from "../i18n";
import { useMotionPrefs } from "../motion/useMotionPrefs";
import type { AttackSurfaceNode } from "../scene/AttackSurfaceScene";

const AttackSurfaceScene = lazy(() => import("../scene/AttackSurfaceScene"));

export interface AttackSurfaceItem extends AttackSurfaceNode {
  type: string;
  status: string;
}

interface AttackSurfacePanelProps {
  target: string;
  items: AttackSurfaceItem[];
}

type SceneMode = "3d" | "reduce" | "unsupported";

/** WebGL 探测只在用户点开时做一次，失败就退回表格，不下载 3D chunk */
function detectMode(reduceMotion: boolean): SceneMode {
  if (reduceMotion) return "reduce";
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    return context ? "3d" : "unsupported";
  } catch {
    return "unsupported";
  }
}

export function AttackSurfacePanel({ target, items }: AttackSurfacePanelProps) {
  const { t } = useT();
  const { reduce } = useMotionPrefs();
  const [expanded, setExpanded] = useState(false);
  const [mode, setMode] = useState<SceneMode | null>(null);

  const serious = items.filter((item) => {
    const key = item.severity.toLowerCase();
    return key === "critical" || key === "high";
  }).length;

  function toggle() {
    if (!expanded) setMode(detectMode(reduce));
    setExpanded((current) => !current);
  }

  return (
    <SectionCard
      title={t("risk.attack_surface")}
      copy={t("risk.attack_surface_copy")}
      aside={<span className="status-badge">{t("risk.attack_surface_summary", { count: String(items.length), serious: String(serious) })}</span>}
    >
      <div className="attack-surface">
        <div className="attack-surface-actions">
          <button type="button" className="secondary-btn" onClick={toggle} aria-expanded={expanded}>
            {expanded ? t("risk.attack_surface_collapse") : t("risk.attack_surface_expand")}
          </button>
          <p className="inline-note">{expanded ? t("risk.attack_surface_hint") : t("risk.attack_surface_idle")}</p>
        </div>

        {expanded && (
          <>
            <div className={`attack-surface-canvas mode-${mode ?? "unsupported"}`}>
              {mode === "3d" ? (
                <Suspense fallback={<div className="empty-state">{t("risk.attack_surface_loading")}</div>}>
                  <AttackSurfaceScene
                    target={target}
                    nodes={items.map((item) => ({ id: item.id, label: item.label, severity: item.severity }))}
                  />
                </Suspense>
              ) : (
                <div className="empty-state">
                  {mode === "reduce" ? t("risk.attack_surface_reduced") : t("risk.attack_surface_unsupported")}
                </div>
              )}
            </div>

            <table className="attack-surface-table">
              <caption className="inline-note">{t("risk.attack_surface_caption")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("risk.attack_surface_col_finding")}</th>
                  <th scope="col">{t("risk.attack_surface_col_severity")}</th>
                  <th scope="col">{t("risk.attack_surface_col_type")}</th>
                  <th scope="col">{t("risk.attack_surface_col_status")}</th>
                </tr>
              </thead>
              <tbody>
                {items.slice(0, 8).map((item) => (
                  <tr key={item.id}>
                    <td>{item.label}</td>
                    <td>{item.severity}</td>
                    <td>{item.type}</td>
                    <td>{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {items.length > 8 && <p className="inline-note">{t("risk.attack_surface_more", { count: String(items.length - 8) })}</p>}
          </>
        )}
      </div>
    </SectionCard>
  );
}