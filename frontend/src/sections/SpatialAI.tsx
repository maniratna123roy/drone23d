import { useQuery } from "@tanstack/react-query";
import { motion, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Reveal, SectionLabel } from "@/components/Reveal";
import { SceneCanvas } from "@/components/three/SceneCanvas";
import {
  CameraRig,
  GroundGrid,
  PointCloud,
  Roads,
  SpatialObjects,
} from "@/components/three/SpatialScene";
import { api } from "@/lib/api";
import { sceneSync } from "@/lib/mockApi";
import { useScrollProgressRef } from "@/lib/useScrollProgressRef";

export function SpatialAI() {
  const section = useRef<HTMLElement>(null);
  const inView = useInView(section, { once: true, margin: "-25%" });
  const { progress } = useScrollProgressRef(section);
  const { data: queries } = useQuery({
    queryKey: ["queries"],
    queryFn: api.getQueries,
  });

  const [step, setStep] = useState(0);
  const [typed, setTyped] = useState("");
  const [answered, setAnswered] = useState(false);

  const current = queries?.[step];

  useEffect(() => {
    if (!inView || !current) return;
    setTyped("");
    setAnswered(false);
    let i = 0;
    const typer = setInterval(() => {
      i += 1;
      setTyped(current.prompt.slice(0, i));
      if (i >= current.prompt.length) {
        clearInterval(typer);
        setTimeout(() => setAnswered(true), 500);
      }
    }, 34);
    return () => clearInterval(typer);
  }, [inView, current]);

  useEffect(() => {
    if (!answered || !queries) return;
    const next = setTimeout(
      () => setStep((s) => (s + 1) % queries.length),
      5200,
    );
    return () => clearTimeout(next);
  }, [answered, queries]);

  return (
    <section
      ref={section}
      id="spatial-ai"
      className="relative border-t border-border py-32"
    >
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="04">Spatial AI</SectionLabel>
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="mt-8 font-display text-[clamp(2rem,4.6vw,4rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            Ask the <span className="text-accent">environment.</span>
          </h2>
        </Reveal>

        <div className="mt-16 grid gap-10 lg:grid-cols-2">
          <Reveal delay={0.15}>
            <div className="relative aspect-[4/3] w-full border border-border lg:aspect-auto lg:h-full lg:min-h-[420px]">
              <SceneCanvas
                className="absolute inset-0"
                camera={{ position: [0, 7, 17], fov: 40 }}
              >
                <CameraRig
                  progressRef={progress}
                  from={[-6, 8, 19]}
                  to={[5, 5, 14]}
                  sway={0.35}
                />
                <GroundGrid />
                <PointCloud count={2200} />
                <Roads />
                <SpatialObjects
                  objects={sceneSync.objects}
                  highlightIds={answered ? (current?.matchedObjectIds ?? []) : []}
                />
              </SceneCanvas>
              <span className="label-tech absolute top-3 left-4">
                Scene {sceneSync.id}
              </span>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="flex h-full flex-col border border-border bg-surface/60">
              <div className="flex items-center justify-between border-b border-border px-5 py-3">
                <span className="label-tech">Spatial Console</span>
                <span className="flex items-center gap-2">
                  <span className="h-[6px] w-[6px] animate-pulse bg-accent" />
                  <span className="label-tech">Connected</span>
                </span>
              </div>

              <div className="flex-1 space-y-8 p-6 font-mono text-sm">
                <div>
                  <p className="label-tech">User</p>
                  <p className="mt-2 text-foreground">
                    {typed}
                    <span className="ml-0.5 inline-block h-4 w-[7px] translate-y-[2px] animate-pulse bg-accent" />
                  </p>
                </div>

                <motion.div
                  animate={{ opacity: answered ? 1 : 0, y: answered ? 0 : 10 }}
                  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                >
                  <p className="label-tech">Result</p>
                  <p className="mt-3 font-display text-[clamp(2rem,5vw,3.4rem)] leading-none tracking-[-0.03em] text-accent">
                    {current?.resultValue}
                  </p>
                  <p className="label-tech mt-3">{current?.resultLabel}</p>
                  <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-4">
                    {[
                      ["PostGIS", "Index"],
                      ["180 MS", "Latency"],
                      ["0.93", "Confidence"],
                    ].map(([v, l]) => (
                      <div key={l}>
                        <p className="text-xs text-foreground">{v}</p>
                        <p className="label-tech mt-1">{l}</p>
                      </div>
                    ))}
                  </div>
                </motion.div>
              </div>

              <div className="flex gap-2 border-t border-border px-5 py-3">
                {(queries ?? []).map((q, i) => (
                  <button
                    key={q.id}
                    onClick={() => setStep(i)}
                    aria-label={q.prompt}
                    className={`h-px w-10 transition-colors ${
                      i === step ? "bg-accent" : "bg-border-strong"
                    }`}
                  />
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
