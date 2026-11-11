import { useMemo, useRef } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import type { AttackSurfaceNode } from "./types";

export interface AttackSurfaceSceneProps {
  target: string;
  nodes: AttackSurfaceNode[];
}

/** 节点上限：超过就截断，避免低端机掉帧 */
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

/**
 * 黄金角球面分布：确定性、无物理引擎。
 * 同一份发现列表每次打开位置一致，便于截图比对。
 */
function layout(count: number): THREE.Vector3[] {
  const positions: THREE.Vector3[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let index = 0; index < count; index += 1) {
    const y = count === 1 ? 0 : 1 - (index / (count - 1)) * 1.5;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * index;
    positions.push(new THREE.Vector3(Math.cos(theta) * radius * 1.75, y * 1.35, Math.sin(theta) * radius * 1.75));
  }
  return positions;
}

/** 所有连线合成一个 geometry：一次 draw call，省得每根线一个材质 */
function useEdgeGeometry(positions: THREE.Vector3[]): THREE.BufferGeometry {
  return useMemo(() => {
    const points: number[] = [];
    for (const position of positions) {
      points.push(0, 0, 0, position.x, position.y, position.z);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    return geometry;
  }, [positions]);
}

function Surface({ nodes }: { nodes: AttackSurfaceNode[] }) {
  const positions = useMemo(() => layout(nodes.length), [nodes.length]);
  const edges = useEdgeGeometry(positions);
  const group = useRef<THREE.Group>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);
  const { invalidate } = useThree();

  function onPointerDown(event: ThreeEvent<PointerEvent>) {
    drag.current = { x: event.clientX, y: event.clientY };
  }

  function onPointerMove(event: ThreeEvent<PointerEvent>) {
    if (!drag.current || !group.current) return;
    const deltaX = event.clientX - drag.current.x;
    const deltaY = event.clientY - drag.current.y;
    drag.current = { x: event.clientX, y: event.clientY };
    group.current.rotation.y += deltaX * 0.006;
    group.current.rotation.x = Math.max(-0.6, Math.min(0.6, group.current.rotation.x + deltaY * 0.004));
    invalidate();
  }

  function onPointerUp() {
    drag.current = null;
  }

  return (
    <group ref={group} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}>
      <mesh>
        <icosahedronGeometry args={[0.42, 2]} />
        <meshStandardMaterial color="#2f6df6" roughness={0.35} metalness={0.15} />
      </mesh>
      {nodes.map((node, index) => (
        <mesh key={node.id} position={positions[index]}>
          <sphereGeometry args={[sizeFor(node.severity), 16, 16]} />
          <meshStandardMaterial
            color={colorFor(node.severity)}
            roughness={0.4}
            metalness={0.1}
            emissive={colorFor(node.severity)}
            emissiveIntensity={0.25}
          />
        </mesh>
      ))}
      {nodes.length > 0 && (
        <lineSegments geometry={edges}>
          <lineBasicMaterial color="#3a5c8f" transparent opacity={0.55} />
        </lineSegments>
      )}
    </group>
  );
}

export default function AttackSurfaceScene({ target, nodes }: AttackSurfaceSceneProps) {
  const visible = nodes.slice(0, MAX_NODES);

  return (
    <Canvas
      dpr={[1, 1.5]}
      frameloop="demand"
      camera={{ position: [0, 1.5, 5.2], fov: 42 }}
      gl={{ antialias: true, alpha: true }}
      data-target={target}
      aria-hidden="true"
    >
      <ambientLight intensity={0.85} />
      <directionalLight position={[3, 4, 5]} intensity={0.9} />
      <Surface nodes={visible} />
    </Canvas>
  );
}