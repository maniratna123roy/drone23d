import { Canvas, type CanvasProps } from "@react-three/fiber";
import { useInView, useReducedMotion } from "motion/react";
import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { SCENE_COLORS } from "./scene-utils";

interface SceneCanvasProps {
  children: ReactNode;
  className?: string;
  camera?: CanvasProps["camera"];
  /** Render even when offscreen (rarely needed). */
  alwaysOn?: boolean;
  /** Verified scenes preserve source COLMAP coordinates; no assumed ground/up transform. */
  sourceFrame?: "COLMAP_PHASE_A";
}

/**
 * Canvas wrapper that only renders while visible — keeps the landing page
 * light on laptops and phones.
 */
export function SceneCanvas({
  children,
  className,
  camera,
  alwaysOn = false,
  sourceFrame,
}: SceneCanvasProps) {
  const host = useRef<HTMLDivElement>(null);
  const inView = useInView(host, { margin: "120px" });
  const reduced = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const verified = sourceFrame === "COLMAP_PHASE_A";
  const frameloop = alwaysOn || inView ? (reduced || verified ? "demand" : "always") : "never";

  return (
    <div ref={host} className={className}>
      {mounted && (
      <Canvas
        frameloop={frameloop}
        dpr={[1, 1.75]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={camera ?? { position: [0, 7, 18], fov: 42 }}
        fallback={<div role="alert" className="p-6">WebGL is unavailable. Enable browser hardware acceleration to view this verified scene.</div>}
      >
        <color attach="background" args={[verified ? "#000000" : SCENE_COLORS.background]} />
        {!verified && <fog attach="fog" args={[SCENE_COLORS.background, 22, 62]} />}
        <ambientLight intensity={0.7} />
        <directionalLight position={[8, 16, 10]} intensity={1.1} />
        <directionalLight
          position={[-12, 6, -8]}
          intensity={0.4}
          color={SCENE_COLORS.accent}
        />
        {/* One frame transform only. The landing showcase keeps its legacy layout;
            unaligned Phase D COLMAP data uses the identity, including its source camera. */}
        <group name="sceneRoot" rotation={[verified ? 0 : Math.PI / -2, 0, 0]}>
          <Suspense fallback={null}>{children}</Suspense>
        </group>
      </Canvas>
      )}
    </div>
  );
}
