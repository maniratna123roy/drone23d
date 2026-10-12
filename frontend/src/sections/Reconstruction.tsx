import { useRef } from "react";
import { Reveal, SectionLabel } from "@/components/Reveal";
import { SceneCanvas } from "@/components/three/SceneCanvas";
import {
  CameraRig,
  ElevationContours,
  GroundGrid,
  PointCloud,
  SpatialObjects,
} from "@/components/three/SpatialScene";
import { sceneSync } from "@/lib/mockApi";
import { useScrollProgressRef } from "@/lib/useScrollProgressRef";

const FLOATING_LABELS = [
  { text: "Camera Pose", top: "18%", left: "10%" },
  { text: "Point Cloud", top: "34%", left: "72%" },
  { text: "Elevation", top: "66%", left: "16%" },
  { text: "Depth", top: "78%", left: "62%" },
];

export function Reconstruction() {
  const section = useRef<HTMLElement>(null);
  const { progress } = useScrollProgressRef(section, [
    "start end",
    "end start",
  ]);

  return (
    <section
      ref={section}
      id="reconstruction"
      className="relative h-[240vh] border-t border-border"
    >
      <div className="sticky top-0 h-screen overflow-hidden">
        <SceneCanvas
          className="absolute inset-0"
          camera={{ position: [0, 6, 20], fov: 42 }}
        >
          <CameraRig
            progressRef={progress}
            from={[0, 12, 26]}
            to={[0, 3.2, 10]}
            sway={0.9}
          />
          <GroundGrid />
          <PointCloud progressRef={progress} count={5200} />
          <ElevationContours progressRef={progress} rows={26} />
          <SpatialObjects objects={sceneSync.objects} progressRef={progress} />
        </SceneCanvas>

        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,transparent_35%,var(--background)_95%)]" />

        {FLOATING_LABELS.map((l) => (
          <span
            key={l.text}
            className="label-tech pointer-events-none absolute hidden border-l border-accent-dim pl-3 md:block"
            style={{ top: l.top, left: l.left }}
          >
            {l.text}
          </span>
        ))}

        <div className="relative mx-auto flex h-full max-w-[1400px] flex-col justify-between px-6 py-28 lg:px-10">
          <div>
            <Reveal>
              <SectionLabel index="02">Reconstruction</SectionLabel>
            </Reveal>
            <Reveal delay={0.1}>
              <h2 className="mt-8 font-display text-[clamp(2.2rem,5.5vw,4.8rem)] leading-[1] font-medium tracking-[-0.03em]">
                Reality, <span className="text-accent">reconstructed.</span>
              </h2>
            </Reveal>
          </div>

          <div className="flex flex-wrap items-end justify-between gap-8">
            <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
              Structure-from-motion recovers camera poses, then dense depth and
              splat reconstruction resolve scattered points into geometry you can
              trust.
            </p>
            <div className="flex gap-10">
              {[
                ["1,204", "Camera poses"],
                ["8.4 M", "Points"],
                ["0.42 PX", "Mean error"],
              ].map(([v, l]) => (
                <div key={l}>
                  <p className="font-mono text-sm text-foreground">{v}</p>
                  <p className="label-tech mt-1">{l}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
