import { motion, useMotionValueEvent, useScroll } from "motion/react";
import { useState } from "react";

const LINKS = [
  { label: "Platform", href: "#platform" },
  { label: "Technology", href: "#technology" },
  { label: "Applications", href: "#applications" },
  { label: "Spatial AI", href: "#spatial-ai" },
];

export function Navbar() {
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setSolid(v > 60));

  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-500 ${
        solid
          ? "border-b border-border bg-background/80 backdrop-blur-md"
          : "border-b border-transparent"
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-6 lg:px-10">
        <a href="#top" className="flex items-center gap-3">
          <span className="relative block h-3 w-3">
            <span className="absolute inset-0 border border-accent" />
            <span className="absolute inset-[3px] bg-accent" />
          </span>
          <span className="font-display text-sm tracking-[0.3em] text-foreground uppercase">
            Vantage
          </span>
          <span className="label-tech hidden sm:block">Spatial</span>
        </a>

        <div className="hidden items-center gap-2 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="border border-border-strong px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase transition-colors hover:border-accent hover:bg-accent hover:text-accent-foreground"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2.5">
          <a
            href="/vantagecam"
            className="flex items-center gap-2 border border-blue-500/80 bg-blue-500/10 px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-blue-300 uppercase transition-colors hover:bg-blue-600 hover:text-white"
          >
            VantageCam 3D
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
          </a>
          <a
            href="/openrouter-3d"
            className="flex items-center gap-2 border border-emerald-500/80 bg-emerald-500/10 px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-emerald-300 uppercase transition-colors hover:bg-emerald-600 hover:text-white"
          >
            OpenRouter AI 3D
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </a>
          <a
            href="/videogrammetry"
            className="flex items-center gap-2 border border-purple-500/80 bg-purple-500/10 px-3 py-2 font-mono text-[10px] tracking-[0.16em] text-purple-300 uppercase transition-colors hover:bg-purple-600 hover:text-white"
          >
            Videogrammetry Approach
            <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
          </a>
          <a
            href="/demo"
            className="flex items-center gap-2 border border-cyan-500 bg-cyan-500/10 px-4 py-2 font-mono text-[10px] tracking-[0.16em] text-cyan-400 uppercase transition-colors hover:bg-cyan-500 hover:text-black"
          >
            Launch 3D Twin
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </a>
        </div>
      </nav>
    </motion.header>
  );
}
