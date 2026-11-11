import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LazyMotion, MotionConfig, domAnimation } from "motion/react";
import { I18nProvider } from "../../i18n";
import type { TaskEvent, TaskRecord } from "../../types/api";
import { SectionCard } from "../SectionCard";
import { StatusDot } from "../StatusDot";
import { Topbar } from "../Topbar";
import { Sidebar } from "../Sidebar";
import { ConfirmDialog } from "../ConfirmDialog";
import { ToastHost } from "../ToastHost";
import { CountUp } from "../CountUp";
import { ActiveTaskBanner } from "../ActiveTaskBanner";
import { AttackSurfacePanel } from "../AttackSurfacePanel";
import { ReportPreviewDialog } from "../ReportPreviewDialog";

function renderWithProviders(ui: React.ReactNode) {
  return render(
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="always">
        <I18nProvider>{ui}</I18nProvider>
      </MotionConfig>
    </LazyMotion>,
  );
}

const task = {
  task_id: "t1",
  command: "recon",
  target: "example.com",
  status: "running",
  created_at: "2026-11-11T00:00:00",
  resume: true,
  options: {},
} as unknown as TaskRecord;

const event: TaskEvent = {
  event: "task_started",
  task_id: "t1",
  timestamp: "2026-11-11T00:00:00",
  payload: { phase: "recon", text: "recon running" },
};

describe("small components", () => {
  it("renders SectionCard, StatusDot and Topbar", () => {
    renderWithProviders(
      <>
        <SectionCard title="Title" copy="Copy" aside={<span>aside</span>}>
          <div>body</div>
        </SectionCard>
        <StatusDot tone="ok" label="healthy" />
        <Topbar eyebrow="eyebrow" title="Title" copy="copy" selectedTarget="example.com" activeTaskStatus="running" />
      </>,
    );
    expect(screen.getAllByText("Title").length).toBeGreaterThan(0);
    expect(screen.getByText("body")).toBeInTheDocument();
    expect(screen.getByText("healthy")).toBeInTheDocument();
    expect(screen.getByText(/example.com/)).toBeInTheDocument();
  });

  it("selects sidebar items", async () => {
    const onSelect = vi.fn();
    renderWithProviders(
      <Sidebar
        activeView="home"
        nav={[
          { key: "home", label: "Home", description: "d", icon: "home" },
          { key: "risk", label: "Risk", description: "d", icon: "risk" },
        ]}
        footerActions={[]}
        onSelectView={onSelect}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Risk" }));
    expect(onSelect).toHaveBeenCalledWith("risk");
  });
});

describe("dialogs and toasts", () => {
  it("handles ConfirmDialog confirm/cancel/Esc", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const { rerender } = renderWithProviders(
      <ConfirmDialog open title="Sure?" copy="Do it" onConfirm={onConfirm} onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /确认|Confirm/ }));
    expect(onConfirm).toHaveBeenCalled();
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalled();
    rerender(
      <LazyMotion features={domAnimation} strict>
        <MotionConfig reducedMotion="always">
          <I18nProvider>
            <ConfirmDialog open={false} title="Sure?" copy="Do it" onConfirm={onConfirm} onCancel={onCancel} />
          </I18nProvider>
        </MotionConfig>
      </LazyMotion>,
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("renders toasts and handles dismiss/action", async () => {
    const onDismiss = vi.fn();
    const onAction = vi.fn();
    renderWithProviders(
      <ToastHost
        toasts={[{ id: 1, tone: "success", title: "Done", copy: "ok", actionLabel: "Open", onAction }]}
        onDismiss={onDismiss}
      />,
    );
    expect(screen.getByText("Done")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(onAction).toHaveBeenCalled();
    expect(onDismiss).toHaveBeenCalledWith(1);
  });

  it("renders report preview and closes", async () => {
    const onClose = vi.fn();
    renderWithProviders(
      <ReportPreviewDialog open title="Report" content="# hello" kind="markdown" loading={false} onClose={onClose} />,
    );
    expect(screen.getByText("# hello")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /关闭|Close/ }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("task surfaces", () => {
  it("shows task banner actions", async () => {
    const onStop = vi.fn();
    const onReports = vi.fn();
    renderWithProviders(
      <ActiveTaskBanner
        task={task}
        latestEvent={event}
        onOpenBoundary={vi.fn()}
        onOpenAdvanced={vi.fn()}
        onOpenReports={onReports}
        onOpenTarget={vi.fn()}
        onStop={onStop}
      />,
    );
    expect(screen.getByText(/example.com/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /停止|Stop/ }));
    expect(onStop).toHaveBeenCalled();
  });

  it("expands the attack surface fallback table", async () => {
    renderWithProviders(
      <AttackSurfacePanel
        target="example.com"
        items={[{ id: "f1", label: "SQLi", severity: "High", type: "SQLi", status: "verified" }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Open 3D view|展开/ }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByText("SQLi").length).toBeGreaterThan(0);
  });

  it("counts up to the final value", async () => {
    renderWithProviders(<CountUp value={42} suffix="%" />);
    await waitFor(() => expect(screen.getByText(/42%/)).toBeInTheDocument(), { timeout: 2000 });
  });
});
