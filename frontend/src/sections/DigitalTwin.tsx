import { OrbitControls } from "@react-three/drei";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Reveal, SectionLabel } from "@/components/Reveal";
import { SceneCanvas } from "@/components/three/SceneCanvas";
import {
  ElevationContours,
  GroundGrid,
  PointCloud,
  Roads,
  SpatialObjects,
} from "@/components/three/SpatialScene";
import { api } from "@/lib/api";
import { sceneSync } from "@/lib/mockApi";
import type { LayerId, SpatialObject } from "@/types/spatial";

export function DigitalTwin() {
  const { data: scene } = useQuery({ queryKey: ["scene"], queryFn: api.getScene });
  const [selected, setSelected] = useState<SpatialObject | null>(null);
  const [hovered, setHovered] = useState<SpatialObject | null>(null);
  const [active, setActive] = useState<LayerId[]>([
    "buildings",
    "roads",
    "terrain",
    "vegetation",
    "infrastructure",
  ]);

  const toggle = (id: LayerId) =>
    setActive((cur) =>
      cur.includes(id) ? cur.filter((l) => l !== id) : [...cur, id],
    );

  const info = selected ?? hovered;

  return (
    <section className="relative border-t border-border py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="06">Digital Twin</SectionLabel>
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="mt-8 font-display text-[clamp(2rem,4.6vw,4rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            Your environment.
            <br />
            <span className="text-accent">Queryable.</span>
          </h2>
        </Reveal>
      </div>

      <Reveal delay={0.15}>
        <div className="relative mt-16 h-[78vh] min-h-[520px] w-full border-y border-border">
          <SceneCanvas
            className="absolute inset-0"
            camera={{ position: [14, 10, 18], fov: 38 }}
          >
            <OrbitControls
              enablePan={false}
              enableDamping
              dampingFactor={0.08}
              minDistance={9}
              maxDistance={38}
              maxPolarAngle={Math.PI / 2.15}
              autoRotate
              autoRotateSpeed={0.28}
              target={[0, 1, 0]}
            />
            <GroundGrid size={70} divisions={46} />
            {active.includes("terrain") && (
              <>
                <PointCloud count={3200} />
                <ElevationContours />
              </>
            )}
            {active.includes("roads") && <Roads />}
            <SpatialObjects
              objects={sceneSync.objects}
              visibleLayers={active}
              interactive
              selectedId={selected?.id ?? null}
              highlightIds={hovered ? [hovered.id] : []}
              onSelect={(o) => setSelected(o)}
              onHover={(o) => setHovered(o)}
            />
          </SceneCanvas>

          <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between p-5">
            <span className="label-tech">
              Drag to orbit · Scroll to zoom · Click an object
            </span>
            <span className="label-tech">
              {sceneSync.boundsM[0]} × {sceneSync.boundsM[1]} M
            </span>
          </div>

          <div className="pointer-events-auto absolute bottom-5 left-5 flex flex-wrap gap-2">
            {(scene?.layers ?? []).map((l) => {
              const on = active.includes(l.id);
              return (
                <button
                  key={l.id}
                  onClick={() => toggle(l.id)}
                  className={`border px-3 py-1.5 font-mono text-[10px] tracking-[0.18em] uppercase transition-colors ${
                    on
                      ? "border-accent text-accent"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {l.label}
                </button>
              );
            })}
          </div>

          <AnimatePresence>
            {info && (
              <motion.div
                key={info.id}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 16 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="absolute top-16 right-5 w-60 border border-border bg-background/85 p-5 backdrop-blur-sm"
              >
                <p className="font-display text-sm tracking-[0.12em] uppercase">
                  {info.label}
                </p>
                <div className="mt-4 space-y-2">
                  {[
                    ["Height", `${info.height.toFixed(1)} M`],
                    ["Elevation", `${info.elevationM.toFixed(1)} M`],
                    ["Area", `${info.areaM2.toLocaleString()} M²`],
                    ["Class", info.layer],
                  ].map(([l, v]) => (
                    <div
                      key={l}
                      className="flex items-baseline justify-between border-b border-border pb-1.5"
                    >
                      <span className="label-tech">{l}</span>
                      <span className="font-mono text-xs text-foreground">
                        {v}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Reveal>
    </section>
  );
}
