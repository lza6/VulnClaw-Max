import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "../../i18n";

const { getStorage, runGc } = vi.hoisted(() => ({
  getStorage: vi.fn(async () => ({
    sessions_bytes: 1024,
    runs_bytes: 2048,
    targets_bytes: 0,
    projects_bytes: 0,
    web_events_bytes: 512,
    web_tasks_bytes: 128,
    total_bytes: 3712,
  })),
  runGc: vi.fn(async () => ({ removed: 2, freed_bytes: 2048, dry_run: true, entries: [] })),
}));

vi.mock("../../api/web", () => ({ getStorage, runGc }));

import { StoragePanel } from "../StoragePanel";

describe("StoragePanel", () => {
  it("shows usage and runs a dry-run gc", async () => {
    render(
      <I18nProvider>
        <StoragePanel />
      </I18nProvider>,
    );
    await waitFor(() => expect(screen.getByText("1.0 KB")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /预览清理|Preview cleanup/ }));
    await waitFor(() => expect(runGc).toHaveBeenCalledWith({ older_than: 30, keep_last: 50, dry_run: true }));
    expect(screen.getAllByText(/2\.0 KB/).length).toBeGreaterThan(0);
  });
});
