import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { applyTheme, resolveTheme, systemPrefersDark, useThemeMode, THEME_COLORS } from "../theme";
import { UI_PREFERENCES_EVENT } from "../preferences";

describe("theme resolution", () => {
  it("honours explicit preferences", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("follows the system preference for auto", () => {
    expect(resolveTheme("auto", true)).toBe("dark");
    expect(resolveTheme("auto", false)).toBe("light");
  });

  it("detects the system preference through matchMedia", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    expect(systemPrefersDark()).toBe(true);
    vi.unstubAllGlobals();
  });

  it("writes data-theme and theme-color", () => {
    document.head.innerHTML = '<meta name="theme-color" content="#000" />';
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute("content")).toBe(THEME_COLORS.dark);
  });
});


describe("useThemeMode", () => {
  it("applies and follows preference changes", async () => {
    const key = "vulnclaw.ui.preferences";
    localStorage.setItem(key, JSON.stringify({ theme: "dark" }));
    const { unmount } = renderHook(() => useThemeMode());
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));

    localStorage.setItem(key, JSON.stringify({ theme: "light" }));
    window.dispatchEvent(new CustomEvent(UI_PREFERENCES_EVENT));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    unmount();
  });
});
