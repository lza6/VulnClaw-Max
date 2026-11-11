import type { AttackSurfaceNode } from "./types";

const MAX_NODES = 60;

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#ff6b6b",
  high: "#ff8b82",
  medium: "#f7c86a",
  low: "#6aa3ff",
  info: "#9db0cc",
};

function colorFor(severity: string): string {
  return SEVERITY_COLOR[severity.toLowerCase()] ?? SEVERITY_COLOR.info;
}

function sizeFor(severity: string): number {
  const key = severity.toLowerCase();
  if (key === "critical") return 0.17;
  if (key === "high") return 0.14;
  if (key === "medium") return 0.12;
  return 0.1;
}

function layout(count: number): Array<{ x: number; y: number }> {
  const positions: Array<{ x: number; y: number }> = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let index = 0; index < count; index += 1) {
    const ratio = count === 1 ? 0 : index / (count - 1);
    const radius = 1.15 + ratio * 0.55;
    const theta = golden * index;
    positions.push({ x: Math.cos(theta) * radius, y: Math.sin(theta) * radius * 0.72 });
  }
  return positions;
}

/** Reduced-motion / no-WebGL equivalent: the same golden-angle topology as SVG. */
export function AttackSurfaceStatic({ nodes }: { nodes: AttackSurfaceNode[] }) {
  const visible = nodes.slice(0, MAX_NODES);
  const positions = layout(visible.length);
  return (
    <svg
      className="attack-surface-static"
      viewBox="-2.2 -1.8 4.4 3.6"
      role="presentation"
      aria-hidden="true"
    >
      <circle cx={0} cy={0} r={0.22} fill="#2f6df6" />
      {positions.map((position, index) => (
        <line
          key={`edge-${visible[index]?.id ?? index}`}
          x1={0}
          y1={0}
          x2={position.x}
          y2={position.y}
          stroke="#3a5c8f"
          strokeOpacity={0.55}
          strokeWidth={0.015}
        />
      ))}
      {positions.map((position, index) => {
        const severity = visible[index]?.severity ?? "info";
        return (
          <circle
            key={visible[index]?.id ?? index}
            cx={position.x}
            cy={position.y}
            r={sizeFor(severity) * 0.9}
            fill={colorFor(severity)}
          />
        );
      })}
    </svg>
  );
}
