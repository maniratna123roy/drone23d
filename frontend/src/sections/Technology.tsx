import { motion } from "motion/react";
import { Reveal, SectionLabel } from "@/components/Reveal";

const STACK = [
  { layer: "Capture", items: ["Drone Video", "Telemetry"] },
  {
    layer: "Reconstruction",
    items: ["COLMAP", "3D Gaussian Splatting", "Depth Estimation"],
  },
  { layer: "Understanding", items: ["Semantic Segmentation"] },
  { layer: "Spatial Data", items: ["PostGIS"] },
  { layer: "Spatial AI", items: ["Natural Language → Spatial Operations"] },
  { layer: "Experience", items: ["Three.js / WebGL"] },
];

export function Technology() {
  return (
    <section id="technology" className="relative border-t border-border py-32">
      <div className="pointer-events-none absolute inset-0 grid-backdrop opacity-30" />
      <div className="relative mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="08">Technology</SectionLabel>
        </Reveal>
        <Reveal delay={0.1}>
          <h2 className="mt-8 max-w-3xl font-display text-[clamp(2rem,4.6vw,4rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            Built as a{" "}
            <span className="text-muted-foreground">
              spatial intelligence stack.
            </span>
          </h2>
        </Reveal>

        <div className="mt-20">
          {STACK.map((row, i) => (
            <Reveal key={row.layer} delay={i * 0.07}>
              <div className="group relative grid grid-cols-1 gap-3 border-t border-border py-6 md:grid-cols-[180px_1fr_60px] md:items-center md:gap-10">
                <motion.span
                  initial={{ scaleX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true, margin: "-60px" }}
                  transition={{
                    duration: 1,
                    delay: i * 0.07,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  className="absolute top-0 left-0 h-px w-full origin-left bg-accent-dim"
                />
                <span className="label-tech text-foreground">{row.layer}</span>
                <div className="flex flex-wrap gap-x-8 gap-y-2">
                  {row.items.map((item) => (
                    <span
                      key={item}
                      className="font-mono text-sm text-muted-foreground transition-colors group-hover:text-foreground"
                    >
                      {item}
                    </span>
                  ))}
                </div>
                <span className="hidden font-mono text-[11px] text-accent md:block md:text-right">
                  L{i + 1}
                </span>
              </div>
            </Reveal>
          ))}
          <div className="rule-h" />
        </div>
      </div>
    </section>
  );
}
