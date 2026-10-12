import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Reveal, SectionLabel } from "@/components/Reveal";
import { api } from "@/lib/api";

const TECH_LABELS = ["Camera", "Depth", "Geometry", "Semantics", "Spatial Data"];

const STAGE_TITLES: Record<string, string> = {
  capture: "Drone Capture",
  reconstruction: "Reconstruction",
  semantics: "Semantic Understanding",
  intelligence: "Spatial Intelligence",
};

export function Pipeline() {
  const { data: jobs } = useQuery({
    queryKey: ["pipeline"],
    queryFn: api.getPipeline,
  });

  return (
    <section id="platform" className="relative border-t border-border py-32">
      <div className="pointer-events-none absolute inset-0 grid-backdrop opacity-40" />
      <div className="relative mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="01">Capture → Digital Twin</SectionLabel>
        </Reveal>

        <Reveal delay={0.1}>
          <h2 className="mt-8 max-w-3xl font-display text-[clamp(2rem,4.6vw,4rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            One pass.
            <br />
            <span className="text-muted-foreground">A living spatial model.</span>
          </h2>
        </Reveal>

        <div className="mt-24 grid gap-px md:grid-cols-4">
          {(jobs ?? []).map((job, i) => (
            <Reveal key={job.id} delay={i * 0.12} className="relative">
              <div className="relative h-full pt-10 pr-6">
                <motion.span
                  initial={{ scaleX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{
                    duration: 0.9,
                    delay: i * 0.12,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  className="absolute top-0 left-0 h-px w-full origin-left bg-border-strong"
                />
                <motion.span
                  initial={{ opacity: 0, scale: 0.4 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ duration: 0.6, delay: 0.25 + i * 0.12 }}
                  className="absolute -top-[3px] left-0 h-[7px] w-[7px] bg-accent"
                />

                <p className="font-mono text-[11px] tracking-[0.22em] text-accent">
                  {String(i + 1).padStart(2, "0")}
                </p>
                <h3 className="mt-5 font-display text-xl tracking-[-0.01em]">
                  {STAGE_TITLES[job.stage]}
                </h3>

                <dl className="mt-7 space-y-3">
                  {job.metrics.map((m) => (
                    <div
                      key={m.label}
                      className="flex items-baseline justify-between gap-4 border-b border-border pb-2"
                    >
                      <dt className="label-tech">{m.label}</dt>
                      <dd className="font-mono text-xs text-foreground">
                        {m.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.2}>
          <div className="mt-20 flex flex-wrap items-center gap-x-10 gap-y-3 border-t border-border pt-6">
            {TECH_LABELS.map((l) => (
              <span key={l} className="label-tech">
                {l}
              </span>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
