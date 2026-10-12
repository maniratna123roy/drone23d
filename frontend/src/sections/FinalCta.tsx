import { useRef } from "react";
import { Reveal } from "@/components/Reveal";
import { SceneCanvas } from "@/components/three/SceneCanvas";
import {
  CameraRig,
  ElevationContours,
  FlightPath,
  PointCloud,
} from "@/components/three/SpatialScene";
import { useScrollProgressRef } from "@/lib/useScrollProgressRef";

export function FinalCta() {
  const section = useRef<HTMLElement>(null);
  const { progress } = useScrollProgressRef(section);

  return (
    <section
      ref={section}
      id="request-demo"
      className="relative overflow-hidden border-t border-border"
    >
      <SceneCanvas
        className="absolute inset-0"
        camera={{ position: [0, 5, 20], fov: 44 }}
      >
        <CameraRig progressRef={progress} from={[0, 6, 24]} to={[0, 3, 16]} />
        <PointCloud count={3000} size={0.04} />
        <ElevationContours />
        <FlightPath speed={0.04} />
      </SceneCanvas>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,transparent_20%,var(--background)_88%)]" />

      <div className="relative mx-auto max-w-[1400px] px-6 py-40 lg:px-10">
        <Reveal>
          <h2 className="max-w-4xl font-display text-[clamp(2.4rem,6.4vw,5.6rem)] leading-[0.98] font-medium tracking-[-0.035em]">
            Reality is only the{" "}
            <span className="text-accent">beginning.</span>
          </h2>
        </Reveal>

        <Reveal delay={0.12}>
          <p className="mt-10 font-mono text-sm leading-relaxed text-muted-foreground">
            Capture once.
            <br />
            Understand everything.
          </p>
        </Reveal>

        <Reveal delay={0.2}>
          <div className="mt-12 flex flex-wrap items-center gap-4">
            <a
              href="#top"
              className="group flex items-center gap-3 bg-accent px-6 py-3 font-mono text-[11px] tracking-[0.18em] text-accent-foreground uppercase transition-opacity hover:opacity-90"
            >
              Explore the digital twin
              <span className="h-px w-5 bg-accent-foreground transition-all group-hover:w-8" />
            </a>
            <a
              href="#request-demo"
              className="border border-border-strong px-6 py-3 font-mono text-[11px] tracking-[0.18em] text-foreground uppercase transition-colors hover:border-accent hover:text-accent"
            >
              Request a demo
            </a>
          </div>
        </Reveal>
      </div>

      <footer className="relative border-t border-border">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-4 px-6 py-8 lg:px-10">
          <span className="label-tech">Vantage Spatial · 2026</span>
          <span className="label-tech">
            47.6205° N / 122.3493° W · Aurora Basin
          </span>
        </div>
      </footer>
    </section>
  );
}
