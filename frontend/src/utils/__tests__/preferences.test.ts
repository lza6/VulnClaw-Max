import { beforeEach, describe, expect, it } from "vitest";

const KEY = "vulnclaw.ui.preferences";

describe("ui preferences", () => {
  beforeEach(() => {
    window.localStorage.clear();
    delete (window as unknown as { __testNavigator?: unknown }).__testNavigator;
  });

  it("falls back to defaults when stored JSON is corrupt", async () => {
    const { loadUiPreferences, DEFAULT_UI_PREFERENCES } = await import("../preferences");
    window.localStorage.setItem(KEY, "{not-json");
    expect(loadUiPreferences().defaultCheckMode).toBe(DEFAULT_UI_PREFERENCES.defaultCheckMode);
  });

  it("normalizes an invalid stored language to English", async () => {
    const { loadUiPreferences } = await import("../preferences");
    window.localStorage.setItem(KEY, JSON.stringify({ language: "fr-FR" }));
    expect(loadUiPreferences().language).toBe("en-US");
  });

  it("round-trips saved preferences", async () => {
    const { loadUiPreferences, saveUiPreferences, DEFAULT_UI_PREFERENCES } = await import("../preferences");
    saveUiPreferences({ ...DEFAULT_UI_PREFERENCES, reportFormat: "html" });
    expect(loadUiPreferences().reportFormat).toBe("html");
  });
});
