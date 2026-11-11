import { describe, expect, it } from "vitest";
import {
  countConstraintViolations,
  formatActionList,
  formatConstraintSummary,
  formatEventLabel,
  formatFindingStatus,
  formatMcpExecutionMode,
  formatMcpHealth,
  formatPhaseLabel,
  formatResumeStrategy,
  formatSeverityLabel,
  formatTaskCommand,
  formatTaskTitle,
} from "../taskLabels";

describe("task label helpers", () => {
  it("formats commands and titles", () => {
    expect(formatTaskCommand("recon")).not.toBe("command.recon");
    expect(formatTaskCommand("unknown-command")).not.toBe("command.unknown-command");
    expect(formatTaskTitle("recon", "example.com")).toContain("example.com");
  });

  it("formats actions and phase labels", () => {
    expect(formatActionList([])).toBeTruthy();
    expect(formatActionList(["recon", "scan"])).toContain(",");
    expect(formatPhaseLabel("vuln_scan")).not.toBe("vuln_scan");
    expect(formatPhaseLabel(null)).toBeTruthy();
  });

  it("maps finding, severity and event labels", () => {
    expect(formatFindingStatus("verified")).not.toBe("finding_status.verified");
    expect(formatFindingStatus("weird")).toBe("weird");
    expect(formatSeverityLabel("Critical")).not.toBe("severity.critical");
    expect(formatSeverityLabel("custom")).toBe("custom");
    expect(formatEventLabel("task_completed")).not.toBe("event.task_completed");
    expect(formatEventLabel("mystery")).toBe("mystery");
  });

  it("maps MCP health, execution mode and resume strategy", () => {
    expect(formatMcpHealth("healthy")).not.toBe("mcp_health.healthy");
    expect(formatMcpExecutionMode("placeholder")).not.toBe("mcp_mode.placeholder");
    expect(formatResumeStrategy("continue_scan")).not.toBe("continue_scan");
    expect(formatResumeStrategy("unknown")).toBe("unknown");
  });

  it("summarises constraints and counts violations", () => {
    const summary = formatConstraintSummary({
      allowed_hosts: ["example.com"],
      allowed_ports: [443],
      blocked_actions: ["exploit"],
    });
    expect(summary).toContain("example.com");
    expect(summary).toContain("443");
    expect(countConstraintViolations([1, 2], undefined)).toBe(2);
    expect(countConstraintViolations(undefined, [1], 0)).toBe(1);
    expect(countConstraintViolations(undefined, undefined, 7)).toBe(7);
  });
});
