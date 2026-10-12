import { Line } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef, type RefObject } from "react";
import * as THREE from "three";
import type { LayerId, SpatialObject } from "@/types/spatial";
import {
  M_PER_UNIT,
  SCENE_COLORS,
  clamp01,
  hash,
  lerp,
  terrainHeight,
} from "./scene-utils";

export type NumberRef = RefObject<number>;

const easeOut = (t: number) => 1 - Math.pow(1 - clamp01(t), 3);

/* ------------------------------------------------------------------ */
/* Point cloud                                                         */
/* ------------------------------------------------------------------ */

interface PointCloudProps {
  progressRef?: NumberRef;
  count?: number;
  spreadX?: number;
  spreadZ?: number;
  size?: number;
  drift?: number;
}

export function PointCloud({
  progressRef,
  count = 3600,
  spreadX = 42,
  spreadZ = 34,
  size = 0.045,
  drift = 0.12,
}: PointCloudProps) {
  const points = useRef<THREE.Points>(null);

  const { positions, targets, scatter, colors } = useMemo(() => {
    const targets = new Float32Array(count * 3);
    const scatter = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const accent = new THREE.Color(SCENE_COLORS.pointAccent);
    const base = new THREE.Color(SCENE_COLORS.point);

    for (let i = 0; i < count; i++) {
      const x = (hash(i * 1.7) - 0.5) * spreadX;
      const z = (hash(i * 3.1 + 5) - 0.5) * spreadZ;
      const y = terrainHeight(x, z) + hash(i * 7.3) * 0.25;
      targets[i * 3] = x;
      targets[i * 3 + 1] = y;
      targets[i * 3 + 2] = z;

      scatter[i * 3] = x + (hash(i * 11.2) - 0.5) * 9;
      scatter[i * 3 + 1] = y + (hash(i * 13.7) - 0.2) * 9;
      scatter[i * 3 + 2] = z + (hash(i * 17.9) - 0.5) * 9;

      const c = hash(i * 23.4) > 0.93 ? accent : base;
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    }
    return { positions: scatter.slice(), targets, scatter, colors };
  }, [count, spreadX, spreadZ]);

  useFrame((state) => {
    const mesh = points.current;
    if (!mesh) return;
    const t = state.clock.elapsedTime;
    const p = easeOut(progressRef?.current ?? 1);
    const attr = mesh.geometry.attributes["position"] as THREE.BufferAttribute;
    const arr = attr.array as Float32Array;
    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      const wob = Math.sin(t * 0.35 + i * 0.13) * drift * (1 - p * 0.75);
      arr[i3] = lerp(scatter[i3]!, targets[i3]!, p);
      arr[i3 + 1] = lerp(scatter[i3 + 1]!, targets[i3 + 1]!, p) + wob;
      arr[i3 + 2] = lerp(scatter[i3 + 2]!, targets[i3 + 2]!, p);
    }
    attr.needsUpdate = true;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={count}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
          count={count}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={size}
        vertexColors
        sizeAttenuation
        transparent
        opacity={0.85}
        depthWrite={false}
      />
    </points>
  );
}

/* ------------------------------------------------------------------ */
/* Elevation contours                                                  */
/* ------------------------------------------------------------------ */

export function ElevationContours({
  progressRef,
  rows = 22,
  spreadX = 40,
  spreadZ = 30,
}: {
  progressRef?: NumberRef;
  rows?: number;
  spreadX?: number;
  spreadZ?: number;
}) {
  const ref = useRef<THREE.LineSegments>(null);

  const geometry = useMemo(() => {
    const pts: number[] = [];
    const cols = 60;
    for (let r = 0; r <= rows; r++) {
      const z = -spreadZ / 2 + (spreadZ * r) / rows;
      for (let c = 0; c < cols; c++) {
        const x0 = -spreadX / 2 + (spreadX * c) / cols;
        const x1 = -spreadX / 2 + (spreadX * (c + 1)) / cols;
        pts.push(x0, terrainHeight(x0, z) - 0.02, z);
        pts.push(x1, terrainHeight(x1, z) - 0.02, z);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [rows, spreadX, spreadZ]);

  useFrame(() => {
    const mat = ref.current?.material as THREE.LineBasicMaterial | undefined;
    if (mat) mat.opacity = 0.05 + easeOut(progressRef?.current ?? 1) * 0.3;
  });

  return (
    <lineSegments ref={ref} geometry={geometry}>
      <lineBasicMaterial
        color={SCENE_COLORS.accentDim}
        transparent
        opacity={0.1}
        depthWrite={false}
      />
    </lineSegments>
  );
}

/* ------------------------------------------------------------------ */
/* Ground grid                                                         */
/* ------------------------------------------------------------------ */

export function GroundGrid({ size = 60, divisions = 40 }) {
  const grid = useMemo(() => {
    const g = new THREE.GridHelper(
      size,
      divisions,
      SCENE_COLORS.accentDim,
      "#1e282b",
    );
    const mat = g.material as THREE.Material;
    mat.transparent = true;
    mat.opacity = 0.35;
    return g;
  }, [size, divisions]);

  return <primitive object={grid} position={[0, -2.2, 0]} />;
}

/* ------------------------------------------------------------------ */
/* Buildings + semantic objects                                        */
/* ------------------------------------------------------------------ */

interface ObjectsProps {
  objects: SpatialObject[];
  progressRef?: NumberRef;
  /** extra metres applied to `extrudeIds`, 0..1 animated */
  extrudeRef?: NumberRef;
  extrudeIds?: string[];
  extrudeMeters?: number;
  highlightIds?: string[];
  visibleLayers?: LayerId[];
  selectedId?: string | null;
  interactive?: boolean;
  onSelect?: (o: SpatialObject | null) => void;
  onHover?: (o: SpatialObject | null) => void;
}

export function SpatialObjects({
  objects,
  progressRef,
  extrudeRef,
  extrudeIds = [],
  extrudeMeters = 0,
  highlightIds = [],
  visibleLayers,
  selectedId,
  interactive = false,
  onSelect,
  onHover,
}: ObjectsProps) {
  const shown = useMemo(
    () =>
      objects.filter((o) => !visibleLayers || visibleLayers.includes(o.layer)),
    [objects, visibleLayers],
  );

  return (
    <group>
      {shown.map((o) => (
        <ObjectMesh
          key={o.id}
          object={o}
          progressRef={progressRef}
          extrudeRef={extrudeIds.includes(o.id) ? extrudeRef : undefined}
          extrudeMeters={extrudeMeters}
          highlighted={highlightIds.includes(o.id) || selectedId === o.id}
          interactive={interactive}
          onSelect={onSelect}
          onHover={onHover}
        />
      ))}
    </group>
  );
}

function ObjectMesh({
  object,
  progressRef,
  extrudeRef,
  extrudeMeters = 0,
  highlighted,
  interactive,
  onSelect,
  onHover,
}: {
  object: SpatialObject;
  progressRef?: NumberRef | undefined;
  extrudeRef?: NumberRef | undefined;
  extrudeMeters?: number | undefined;
  highlighted: boolean;
  interactive?: boolean | undefined;
  onSelect?: ((o: SpatialObject | null) => void) | undefined;
  onHover?: ((o: SpatialObject | null) => void) | undefined;
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const baseY = terrainHeight(object.x, object.z);
  const unitHeight = object.height / M_PER_UNIT;
  const seed = hash(object.x * 3.3 + object.z * 7.7);

  const color =
    object.layer === "vegetation"
      ? SCENE_COLORS.vegetation
      : object.layer === "infrastructure"
        ? SCENE_COLORS.infrastructure
        : SCENE_COLORS.building;

  useFrame((state, delta) => {
    const m = mesh.current;
    if (!m) return;
    const p = clamp01((progressRef?.current ?? 1) * 1.6 - seed * 0.5);
    const extra = (extrudeRef?.current ?? 0) * (extrudeMeters / M_PER_UNIT);
    const target = Math.max(0.001, unitHeight * easeOut(p) + extra);
    m.scale.y = lerp(m.scale.y, target, 1 - Math.exp(-8 * delta));
    m.position.y = baseY + m.scale.y / 2;

    const mat = m.material as THREE.MeshStandardMaterial;
    const glow = highlighted
      ? 0.55 + Math.sin(state.clock.elapsedTime * 2) * 0.12
      : 0;
    mat.emissiveIntensity = lerp(mat.emissiveIntensity, glow, 0.12);
    mat.opacity = lerp(mat.opacity, 0.25 + easeOut(p) * 0.75, 0.1);
  });

  return (
    <mesh
      ref={mesh}
      position={[object.x, baseY, object.z]}
      scale={[1, 0.001, 1]}
      onPointerOver={(e) => {
        if (!interactive) return;
        e.stopPropagation();
        onHover?.(object);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        if (!interactive) return;
        onHover?.(null);
        document.body.style.cursor = "auto";
      }}
      onClick={(e) => {
        if (!interactive) return;
        e.stopPropagation();
        onSelect?.(object);
      }}
    >
      <boxGeometry args={[object.width, 1, object.depth]} />
      <meshStandardMaterial
        color={color}
        emissive={SCENE_COLORS.accent}
        emissiveIntensity={0}
        roughness={0.72}
        metalness={0.06}
        transparent
        opacity={0.3}
      />
    </mesh>
  );
}

/* ------------------------------------------------------------------ */
/* Roads                                                               */
/* ------------------------------------------------------------------ */

export function Roads({ progressRef }: { progressRef?: NumberRef }) {
  const group = useRef<THREE.Group>(null);
  const lines = useMemo(() => {
    const out: { pts: [number, number, number][]; key: string }[] = [];
    for (let i = -3; i <= 3; i++) {
      const z = i * 2.6 - 1.3;
      const pts: [number, number, number][] = [];
      for (let x = -18; x <= 18; x += 1.5)
        pts.push([x, terrainHeight(x, z) + 0.04, z]);
      out.push({ pts, key: `h${i}` });
    }
    for (let i = -2; i <= 2; i++) {
      const x = i * 2.6 - 1.3;
      const pts: [number, number, number][] = [];
      for (let z = -14; z <= 14; z += 1.5)
        pts.push([x, terrainHeight(x, z) + 0.04, z]);
      out.push({ pts, key: `v${i}` });
    }
    return out;
  }, []);

  useFrame(() => {
    if (!group.current) return;
    const p = easeOut(progressRef?.current ?? 1);
    group.current.children.forEach((c) => {
      const mat = (c as THREE.Mesh).material as THREE.Material & {
        opacity: number;
      };
      if (mat) mat.opacity = p * 0.5;
    });
  });

  return (
    <group ref={group}>
      {lines.map((l) => (
        <Line
          key={l.key}
          points={l.pts}
          color={SCENE_COLORS.accent}
          lineWidth={1}
          transparent
          opacity={0.35}
        />
      ))}
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Flight path                                                         */
/* ------------------------------------------------------------------ */

export function FlightPath({ speed = 0.06 }: { speed?: number }) {
  const marker = useRef<THREE.Mesh>(null);

  const curve = useMemo(
    () =>
      new THREE.CatmullRomCurve3(
        Array.from({ length: 40 }, (_, i) => {
          const t = i / 39;
          const a = t * Math.PI * 2;
          return new THREE.Vector3(
            Math.sin(a) * (14 - t * 4),
            5.5 + Math.sin(a * 2) * 0.8,
            Math.cos(a) * (10 - t * 3),
          );
        }),
        true,
      ),
    [],
  );

  const pts = useMemo(
    () => curve.getPoints(160).map((p) => [p.x, p.y, p.z] as [number, number, number]),
    [curve],
  );

  useFrame((state) => {
    if (!marker.current) return;
    const t = (state.clock.elapsedTime * speed) % 1;
    const p = curve.getPointAt(t);
    marker.current.position.copy(p);
  });

  return (
    <group>
      <Line
        points={pts}
        color={SCENE_COLORS.accentDim}
        lineWidth={1}
        transparent
        opacity={0.5}
        dashed
        dashSize={0.6}
        gapSize={0.5}
      />
      <mesh ref={marker}>
        <sphereGeometry args={[0.07, 10, 10]} />
        <meshBasicMaterial color={SCENE_COLORS.accent} />
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Camera rig                                                          */
/* ------------------------------------------------------------------ */

interface CameraRigProps {
  progressRef?: NumberRef | undefined;
  from?: [number, number, number];
  to?: [number, number, number];
  lookAt?: [number, number, number];
  sway?: number;
}

export function CameraRig({
  progressRef,
  from = [0, 8, 22],
  to = [0, 4.5, 12],
  lookAt = [0, 1, 0],
  sway = 0.6,
}: CameraRigProps) {
  const { camera } = useThree();
  const target = useMemo(() => new THREE.Vector3(...lookAt), [lookAt]);

  useFrame((state, delta) => {
    const p = easeOut(progressRef?.current ?? 0);
    const t = state.clock.elapsedTime;
    const x = lerp(from[0], to[0], p) + Math.sin(t * 0.12) * sway;
    const y = lerp(from[1], to[1], p) + Math.sin(t * 0.09) * sway * 0.25;
    const z = lerp(from[2], to[2], p);
    camera.position.x = lerp(camera.position.x, x, 1 - Math.exp(-4 * delta));
    camera.position.y = lerp(camera.position.y, y, 1 - Math.exp(-4 * delta));
    camera.position.z = lerp(camera.position.z, z, 1 - Math.exp(-4 * delta));
    camera.lookAt(target);
  });

  return null;
}

/* ------------------------------------------------------------------ */
/* Coordinate markers                                                  */
/* ------------------------------------------------------------------ */

export function CoordinateMarkers({ count = 7 }: { count?: number }) {
  const items = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const x = (hash(i * 5.5) - 0.5) * 30;
        const z = (hash(i * 9.1 + 3) - 0.5) * 22;
        return { x, z, y: terrainHeight(x, z), key: i };
      }),
    [count],
  );

  return (
    <group>
      {items.map((m) => (
        <Line
          key={m.key}
          points={[
            [m.x, m.y, m.z],
            [m.x, m.y + 1.6, m.z],
          ]}
          color={SCENE_COLORS.accent}
          lineWidth={1}
          transparent
          opacity={0.32}
        />
      ))}
    </group>
  );
}
