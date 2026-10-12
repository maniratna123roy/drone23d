import { motion } from "motion/react";
import { useState } from "react";
import { Reveal, SectionLabel } from "@/components/Reveal";

const APPLICATIONS = [
  {
    id: "disaster",
    title: "Disaster Response",
    note: "Damage deltas within hours of a single pass.",
    metric: "04 H",
    metricLabel: "Turnaround",
  },
  {
    id: "urban",
    title: "Urban Planning",
    note: "Massing studies against a measured baseline.",
    metric: "1,842 M²",
    metricLabel: "Parcel",
  },
  {
    id: "infrastructure",
    title: "Infrastructure",
    note: "Clearance, corridors and asset condition.",
    metric: "42.8 M",
    metricLabel: "Clearance",
  },
  {
    id: "construction",
    title: "Construction",
    note: "Progress against design, week over week.",
    metric: "+3.2 %",
    metricLabel: "Progress",
  },
  {
    id: "environment",
    title: "Environmental Monitoring",
    note: "Canopy, erosion and volumetric change.",
    metric: "8.4 M",
    metricLabel: "Points",
  },
];

/** Lightweight SVG spatial motif — cheaper than a canvas per row. */
function RowMotif({ seed }: { seed: number }) {
  const bars = Array.from({ length: 14 }, (_, i) => {
    const h = 6 + ((Math.sin(i * 1.7 + seed) + 1) / 2) * 30;
    return { x: i * 14 + 4, h };
  });
  return (
    <svg viewBox="0 0 200 48" className="h-12 w-[200px]" aria-hidden>
      <line x1="0" y1="44" x2="200" y2="44" stroke="currentColor" strokeWidth="0.5" />
      {bars.map((b, i) => (
        <motion.rect
          key={i}
          x={b.x}
          y={44 - b.h}
          width="7"
          height={b.h}
          fill="currentColor"
          fillOpacity="0.22"
          stroke="currentColor"
          strokeWidth="0.5"
          initial={{ scaleY: 0, originY: 1 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.5, delay: i * 0.02 }}
          style={{ transformOrigin: `${b.x}px 44px` }}
        />
      ))}
    </svg>
  );
}

export function Applications() {
  const [hover, setHover] = useState<string | null>(null);

  return (
    <section id="applications" className="relative border-t border-border py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal>
          <SectionLabel index="07">Applications</SectionLabel>
        </Reveal>

        <div className="mt-16 border-t border-border-strong">
          {APPLICATIONS.map((app, i) => (
            <Reveal key={app.id} delay={i * 0.06}>
              <div
                onMouseEnter={() => setHover(app.id)}
                onMouseLeave={() => setHover(null)}
                className="group relative grid grid-cols-1 items-center gap-4 border-b border-border py-8 md:grid-cols-[auto_1fr_auto_auto] md:gap-10"
              >
                <span className="font-mono text-[11px] text-accent">
                  {String(i + 1).padStart(2, "0")}
                </span>

                <h3
                  className={`font-display text-[clamp(1.6rem,3.6vw,3rem)] leading-none font-medium tracking-[-0.03em] transition-colors duration-500 ${
                    hover === app.id ? "text-accent" : "text-foreground"
                  }`}
                >
                  {app.title}
                </h3>

                <motion.div
                  animate={{ opacity: hover === app.id ? 1 : 0 }}
                  transition={{ duration: 0.4 }}
                  className="hidden text-accent md:block"
                >
                  {hover === app.id && <RowMotif seed={i * 2.3} />}
                </motion.div>

                <div className="md:text-right">
                  <p className="font-mono text-xs text-foreground">{app.metric}</p>
                  <p className="label-tech mt-1">{app.metricLabel}</p>
                </div>

                <motion.p
                  animate={{
                    opacity: hover === app.id ? 1 : 0,
                    y: hover === app.id ? 0 : 6,
                  }}
                  transition={{ duration: 0.4 }}
                  className="col-span-full -mt-2 text-xs text-muted-foreground md:col-start-2"
                >
                  {app.note}
                </motion.p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
