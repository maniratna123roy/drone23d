import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
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
import { api } from "@/lib/api";
import { sceneSync } from "@/lib/mockApi";
import { useScrollProgressRef } from "@/lib/useScrollProgressRef";
import type { LayerId } from "@/types/spatial";

export function Semantic() {
  const section = useRef<HTMLElement>(null);
  const { progress } = useScrollProgressRef(section);
  const { data: scene } = useQuery({ queryKey: ["scene"], queryFn: api.getScene });

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

  return (
    <section ref={section} className="relative border-t border-border py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="03">Semantic Understanding</SectionLabel>
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="mt-8 max-w-3xl font-display text-[clamp(2rem,4.6vw,4rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            It doesn&apos;t just see.
            <br />
            <span className="text-muted-foreground">It understands space.</span>
          </h2>
        </Reveal>

        <div className="mt-16 grid gap-10 lg:grid-cols-[260px_1fr]">
          <Reveal delay={0.15}>
            <div className="border-t border-border-strong">
              {(scene?.layers ?? []).map((layer) => {
                const on = active.includes(layer.id);
                return (
                  <button
                    key={layer.id}
                    onClick={() => toggle(layer.id)}
                    className="group flex w-full items-center justify-between border-b border-border py-4 text-left transition-colors"
                  >
                    <span className="flex items-center gap-3">
                      <span
                        className={`h-[6px] w-[6px] transition-colors ${
                          on ? "bg-accent" : "bg-border-strong"
                        }`}
                      />
                      <span
                        className={`font-mono text-[11px] tracking-[0.18em] uppercase transition-colors ${
                          on
                            ? "text-foreground"
                            : "text-muted-foreground group-hover:text-foreground"
                        }`}
                      >
                        {layer.label}
                      </span>
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {String(layer.count).padStart(2, "0")}
                    </span>
                  </button>
                );
              })}
              <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
                Every surface is classified, instanced and indexed — so the model
                is data, not decoration.
              </p>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="relative aspect-[16/10] w-full border border-border">
              <SceneCanvas
                className="absolute inset-0"
                camera={{ position: [0, 6, 18], fov: 40 }}
              >
                <CameraRig
                  progressRef={progress}
                  from={[6, 8, 20]}
                  to={[-4, 5, 15]}
                  sway={0.4}
                />
                <GroundGrid />
                {active.includes("terrain") && (
                  <>
                    <PointCloud count={2600} />
                    <ElevationContours />
                  </>
                )}
                {active.includes("roads") && <Roads />}
                <SpatialObjects
                  objects={sceneSync.objects}
                  visibleLayers={active}
                />
              </SceneCanvas>
              <span className="label-tech absolute top-3 left-4">
                Semantic layers · {active.length}/5
              </span>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
