import { useEffect } from "react";
import { loadUiPreferences, subscribeUiPreferences } from "./preferences";

export type ThemePreference = "auto" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/** 与 styles/tokens.css 的 --bg 保持一致，供 <meta name="theme-color"> 使用 */
export const THEME_COLORS: Record<ResolvedTheme, string> = {
  light: "#f4f8fe",
  dark: "#0b1220",
};

export function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : false;
}

export function resolveTheme(preference: ThemePreference, prefersDark = systemPrefersDark()): ResolvedTheme {
  if (preference === "light" || preference === "dark") return preference;
  return prefersDark ? "dark" : "light";
}

export function applyTheme(resolved: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", THEME_COLORS[resolved]);
}

function syncTheme(): void {
  applyTheme(resolveTheme(loadUiPreferences().theme));
}

/**
 * 把用户偏好落到 <html data-theme>，并跟随三处变化：
 * 用户在设置页改了偏好、其他标签页改了偏好、系统外观切换（仅 auto 时生效）。
 */
export function useThemeMode(): void {
  useEffect(() => {
    syncTheme();
    const unsubscribe = subscribeUiPreferences(syncTheme);
    const query = typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)")
      : null;
    const onSystemChange = () => {
      if (loadUiPreferences().theme === "auto") syncTheme();
    };
    query?.addEventListener("change", onSystemChange);
    return () => {
      unsubscribe();
      query?.removeEventListener("change", onSystemChange);
    };
  }, []);
}
