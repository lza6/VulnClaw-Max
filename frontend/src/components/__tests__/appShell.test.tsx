import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LazyMotion, MotionConfig, domAnimation } from "motion/react";
import { I18nProvider } from "../../i18n";
import { AppShell } from "../AppShell";
import { AppErrorBoundary } from "../AppErrorBoundary";

function shell(children: React.ReactNode = <div>page body</div>) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="always">
        <I18nProvider>
          <AppShell
            activeView="home"
            nav={[{ key: "home", label: "Home", description: "d", icon: "home" }]}
            meta={{ eyebrow: "eyebrow", title: "title", copy: "copy" }}
            quickActions={[]}
            sidebarActions={[{ label: "Settings", icon: "settings", onClick: vi.fn() }]}
            selectedTarget="example.com"
            activeTask={null}
            latestEvent={null}
            onSelectView={vi.fn()}
            onOpenAdvanced={vi.fn()}
            onOpenBoundary={vi.fn()}
            onOpenReports={vi.fn()}
            onOpenTarget={vi.fn()}
            onStopTask={vi.fn()}
          >
            {children}
          </AppShell>
        </I18nProvider>
      </MotionConfig>
    </LazyMotion>
  );
}

describe("AppShell", () => {
  it("renders navigation, topbar and page content", () => {
    render(shell());
    expect(screen.getByText("page body")).toBeInTheDocument();
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByText(/example.com/)).toBeInTheDocument();
  });
});

describe("AppErrorBoundary", () => {
  it("renders a fallback when a child throws", () => {
    const Boom = () => {
      throw new Error("boom");
    };
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <AppErrorBoundary>
        <Boom />
      </AppErrorBoundary>,
    );
    expect(screen.getByText(/boom/)).toBeInTheDocument();
    spy.mockRestore();
  });
});
