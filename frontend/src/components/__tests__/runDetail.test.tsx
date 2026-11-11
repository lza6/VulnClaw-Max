import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LazyMotion, MotionConfig, domAnimation } from "motion/react";
import { I18nProvider } from "../../i18n";
import type { RunDetail } from "../../types/api";

const run: RunDetail = {
  run_name: "run-1",
  command: "recon",
  status: "failed",
  created_at: "2026-11-11T00:00:00",
  started_at: "2026-11-11T00:00:00",
  ended_at: "2026-11-11T00:01:00",
  exit_code: 1,
  message: "LLM authentication failed",
  targets: ["https://example.com"],
  run_dir: "run-1",
  artifacts: { events: "events/events.jsonl" },
  resume: { last_snapshot_id: "snap-1" },
  events: [{ timestamp: "2026-11-11T00:00:00", kind: "checkpoint", payload: { i: 1 } }],
  phases: [{ name: "checkpoint", started_at: "2026-11-11T00:00:00", ended_at: "2026-11-11T00:01:00", duration_seconds: 60, event_count: 1 }],
  findings: { findings: [{ finding_id: "f1", title: "SQLi", severity: "High", lifecycle_status: "verified", evidence: "id=1" }] },
  reports: ["report.md"],
};

vi.mock("../../hooks/queries", () => ({
  useRunDetailQuery: () => ({ data: run, isLoading: false, isError: false, error: null }),
}));

import { RunDetailDialog } from "../RunDetailDialog";

function renderDialog(onResume = vi.fn(), onClose = vi.fn()) {
  return render(
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="always">
        <I18nProvider>
          <RunDetailDialog open runName="run-1" onClose={onClose} onResume={onResume} />
        </I18nProvider>
      </MotionConfig>
    </LazyMotion>,
  );
}

describe("RunDetailDialog", () => {
  it("renders failure, phases, evidence and artifacts", () => {
    renderDialog();
    expect(screen.getByText("LLM authentication failed")).toBeInTheDocument();
    expect(screen.getByText("Phase durations")).toBeInTheDocument();
    expect(screen.getAllByText("checkpoint").length).toBeGreaterThan(0);
    expect(screen.getByText("Evidence")).toBeInTheDocument();
    expect(screen.getByText("SQLi")).toBeInTheDocument();
    expect(screen.getByText("report.md")).toBeInTheDocument();
  });

  it("resumes and closes", async () => {
    const onResume = vi.fn();
    const onClose = vi.fn();
    renderDialog(onResume, onClose);
    await userEvent.click(screen.getByRole("button", { name: "Resume" }));
    expect(onResume).toHaveBeenCalledWith(run);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });
});
