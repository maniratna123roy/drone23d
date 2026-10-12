import { useQuery } from "@tanstack/react-query";
import { useFrame } from "@react-three/fiber";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Group } from "three";
import { Reveal, SectionLabel } from "@/components/Reveal";
import { SceneCanvas } from "@/components/three/SceneCanvas";
import {
  CameraRig,
  ElevationContours,
  GroundGrid,
  PointCloud,
  Roads,
  SpatialObjects,
} from "@/components/three/SpatialScene";
import { M_PER_UNIT, lerp } from "@/components/three/scene-utils";
import { api } from "@/lib/api";
import { sceneSync } from "@/lib/mockApi";
import { useScrollProgressRef } from "@/lib/useScrollProgressRef";

/** Lifts the terrain group toward a target height (scene units). */
function TerrainLift({
  targetRef,
  children,
}: {
  targetRef: React.RefObject<number>;
  children: ReactNode;
}) {
  const group = useRef<Group>(null);
  useFrame((_, delta) => {
    if (!group.current) return;
    group.current.position.y = lerp(
      group.current.position.y,
      targetRef.current,
      1 - Math.exp(-3 * delta),
    );
  });
  return <group ref={group}>{children}</group>;
}

export function Editing() {
  const section = useRef<HTMLElement>(null);
  const { progress } = useScrollProgressRef(section);
  const { data: edits } = useQuery({ queryKey: ["edits"], queryFn: api.getEdits });

  const [active, setActive] = useState(0);
  const extrudeRef = useRef(0);
  const liftRef = useRef(0);
  const [applied, setApplied] = useState(false);

  const edit = edits?.[active];

  useEffect(() => {
    if (!edit) return;
    setApplied(false);
    extrudeRef.current = 0;
    liftRef.current = 0;
    const run = setTimeout(() => {
      setApplied(true);
      if (edit.operation === "extrude") extrudeRef.current = 1;
      else liftRef.current = edit.deltaM / M_PER_UNIT;
    }, 900);
    return () => clearTimeout(run);
  }, [edit]);

  return (
    <section ref={section} className="relative border-t border-border py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="05">Generative Editing</SectionLabel>
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="mt-8 max-w-3xl font-display text-[clamp(2rem,4.6vw,4rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            Don&apos;t just analyze reality.
            <br />
            <span className="text-muted-foreground">
              Explore what could change.
            </span>
          </h2>
        </Reveal>

        <div className="mt-16 grid gap-10 lg:grid-cols-[1fr_320px]">
          <Reveal delay={0.15}>
            <div className="relative aspect-[16/10] w-full border border-border">
              <SceneCanvas
                className="absolute inset-0"
                camera={{ position: [0, 6, 18], fov: 40 }}
              >
                <CameraRig
                  progressRef={progress}
                  from={[-8, 7, 20]}
                  to={[4, 4.5, 13]}
                  sway={0.3}
                />
                <GroundGrid />
                <TerrainLift targetRef={liftRef}>
                  <PointCloud count={2400} />
                  <ElevationContours />
                  <Roads />
                </TerrainLift>
                <SpatialObjects
                  objects={sceneSync.objects}
                  extrudeRef={extrudeRef}
                  extrudeIds={
                    edit?.operation === "extrude" ? edit.targetObjectIds : []
                  }
                  extrudeMeters={edit?.deltaM ?? 0}
                  highlightIds={edit?.targetObjectIds ?? []}
                />
              </SceneCanvas>

              <motion.div
                animate={{ opacity: applied ? 1 : 0.35 }}
                className="absolute right-4 bottom-4 border border-border bg-background/85 px-4 py-3 backdrop-blur-sm"
              >
                <div className="flex items-center gap-6">
                  <div>
                    <p className="font-mono text-xs text-foreground">
                      {edit?.status.objects} OBJECTS
                    </p>
                    <p className="label-tech mt-1">Selection</p>
                  </div>
                  <div>
                    <p className="font-mono text-xs text-accent">
                      {edit?.status.delta}
                    </p>
                    <p className="label-tech mt-1">Delta</p>
                  </div>
                  <div>
                    <p className="font-mono text-xs text-foreground">
                      {applied ? edit?.status.state : "Computing"}
                    </p>
                    <p className="label-tech mt-1">Status</p>
                  </div>
                </div>
              </motion.div>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="border-t border-border-strong">
              {(edits ?? []).map((e, i) => (
                <button
                  key={e.id}
                  onClick={() => setActive(i)}
                  className="block w-full border-b border-border py-5 text-left"
                >
                  <span className="label-tech">
                    Command {String(i + 1).padStart(2, "0")}
                  </span>
                  <span
                    className={`mt-2 block font-mono text-sm transition-colors ${
                      i === active ? "text-accent" : "text-muted-foreground"
                    }`}
                  >
                    &ldquo;{e.command}&rdquo;
                  </span>
                </button>
              ))}
              <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
                Edits run as previews on the twin — geometry, elevation and
                semantics stay linked, so every change remains measurable.
              </p>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
