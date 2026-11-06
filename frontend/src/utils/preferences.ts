export type ReportTemplate = "pentest" | "executive" | "ctf";

export type ThemePreference = "auto" | "light" | "dark";

export interface UiPreferences {
  language: "zh-CN" | "en-US";
  defaultCheckMode: "quick" | "standard" | "deep" | "continuous";
  reportFormat: "markdown" | "html";
  reportTemplate: ReportTemplate;
  showTechnicalLogs: boolean;
  theme: ThemePreference;
  defaultBoundary: BoundaryDefaults;
}

export interface BoundaryDefaults {
  onlyPort: string;
  onlyHost: string;
  onlyPath: string;
  blockedHost: string;
  blockedPath: string;
  allowActions: string[];
  blockActions: string[];
}

const STORAGE_KEY = "vulnclaw.ui.preferences";
export const UI_PREFERENCES_EVENT = "vulnclaw.ui.preferences.updated";

/**
 * 首次访问时的界面语言：先看浏览器是否偏好中文/英文，其它语种回落中文。
 * 用户在设置页显式保存过的偏好始终优先（见 loadUiPreferences）。
 */
function detectDefaultLanguage(): UiPreferences["language"] {
  const candidates = typeof navigator === "undefined"
    ? []
    : [...(navigator.languages ?? []), navigator.language];
  for (const tag of candidates) {
    const lowered = String(tag ?? "").toLowerCase();
    if (lowered.startsWith("zh")) return "zh-CN";
    if (lowered.startsWith("en")) return "en-US";
  }
  return "en-US";
}

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  language: detectDefaultLanguage(),
  defaultCheckMode: "standard",
  reportFormat: "markdown",
  reportTemplate: "pentest",
  showTechnicalLogs: false,
  theme: "auto",
  defaultBoundary: {
    onlyPort: "",
    onlyHost: "",
    onlyPath: "",
    blockedHost: "",
    blockedPath: "",
    allowActions: [],
    blockActions: [],
  },
};

export function loadUiPreferences(): UiPreferences {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_UI_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<UiPreferences>;
    return {
      language: parsed.language === "zh-CN" ? "zh-CN" : "en-US",
      defaultCheckMode: isCheckMode(parsed.defaultCheckMode) ? parsed.defaultCheckMode : DEFAULT_UI_PREFERENCES.defaultCheckMode,
      reportFormat: parsed.reportFormat === "html" ? "html" : "markdown",
      reportTemplate: isReportTemplate(parsed.reportTemplate) ? parsed.reportTemplate : "pentest",
      showTechnicalLogs: Boolean(parsed.showTechnicalLogs),
      theme: isThemePreference(parsed.theme) ? parsed.theme : DEFAULT_UI_PREFERENCES.theme,
      defaultBoundary: normalizeBoundaryDefaults(parsed.defaultBoundary),
    };
  } catch {
    return DEFAULT_UI_PREFERENCES;
  }
}

export function saveUiPreferences(preferences: UiPreferences): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  window.dispatchEvent(new CustomEvent<UiPreferences>(UI_PREFERENCES_EVENT, { detail: preferences }));
}

export function subscribeUiPreferences(onChange: (preferences: UiPreferences) => void): () => void {
  const handleLocalUpdate = (event: Event) => {
    const customEvent = event as CustomEvent<UiPreferences>;
    onChange(customEvent.detail ?? loadUiPreferences());
  };
  const handleStorageUpdate = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) onChange(loadUiPreferences());
  };

  window.addEventListener(UI_PREFERENCES_EVENT, handleLocalUpdate);
  window.addEventListener("storage", handleStorageUpdate);

  return () => {
    window.removeEventListener(UI_PREFERENCES_EVENT, handleLocalUpdate);
    window.removeEventListener("storage", handleStorageUpdate);
  };
}

function isReportTemplate(value: unknown): value is UiPreferences["reportTemplate"] {
  return value === "pentest" || value === "executive" || value === "ctf";
}

function isCheckMode(value: unknown): value is UiPreferences["defaultCheckMode"] {
  return value === "quick" || value === "standard" || value === "deep" || value === "continuous";
}

function isThemePreference(value: unknown): value is ThemePreference {
  return value === "auto" || value === "light" || value === "dark";
}

function normalizeBoundaryDefaults(value: unknown): BoundaryDefaults {
  const raw = value && typeof value === "object" ? value as Partial<BoundaryDefaults> : {};
  return {
    onlyPort: typeof raw.onlyPort === "string" ? raw.onlyPort : "",
    onlyHost: typeof raw.onlyHost === "string" ? raw.onlyHost : "",
    onlyPath: typeof raw.onlyPath === "string" ? raw.onlyPath : "",
    blockedHost: typeof raw.blockedHost === "string" ? raw.blockedHost : "",
    blockedPath: typeof raw.blockedPath === "string" ? raw.blockedPath : "",
    allowActions: Array.isArray(raw.allowActions) ? raw.allowActions.map(String) : [],
    blockActions: Array.isArray(raw.blockActions) ? raw.blockActions.map(String) : [],
  };
}
