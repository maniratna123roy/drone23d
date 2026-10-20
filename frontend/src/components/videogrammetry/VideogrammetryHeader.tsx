import React from "react";
import { ArrowLeft, GitCompare, RefreshCw, Layers, ShieldCheck, Box } from "lucide-react";

interface VideogrammetryHeaderProps {
  currentTier: string;
  status: string;
  progress: number;
  onOpenCompare: () => void;
  onReset: () => void;
}

export const VideogrammetryHeader: React.FC<VideogrammetryHeaderProps> = ({
  currentTier,
  status,
  progress,
  onOpenCompare,
  onReset,
}) => {
  return (
    <header className="border-b border-border/80 bg-background/95 backdrop-blur px-6 py-3 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <a
          href="/demo"
          className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-cyan-400 transition-colors border border-border px-2.5 py-1.5 rounded"
          title="Switch to Gaussian Splatting Approach"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Gaussian Splatting</span>
        </a>

        <a
          href="/openrouter-3d"
          className="flex items-center gap-1.5 text-xs font-mono text-emerald-300 hover:text-white transition-colors border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 rounded"
          title="Switch to OpenRouter AI 3D Approach"
        >
          <span>OpenRouter AI 3D</span>
        </a>

        <div className="h-5 w-px bg-border/60" />

        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-purple-500/20 border border-purple-500/40 text-purple-300">
            <Box className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-semibold text-sm tracking-tight text-foreground uppercase">
                VIDEOGRAMMETRY APPROACH
              </h1>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded border border-purple-500/30 bg-purple-950/60 text-purple-300">
                Skyebrowse Model Sidecar
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Continuous drone-video-to-3D · Metric Polygon Mesh · Orthomosaic · AI Quality Redo Loop
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs">
        {/* Tier badge */}
        <div className="flex items-center gap-1.5 border border-border px-3 py-1.5 rounded bg-muted/40 font-mono text-[11px]">
          <span className="text-muted-foreground">Tier:</span>
          <span className="font-semibold text-purple-300 uppercase">{currentTier}</span>
        </div>

        {/* Status badge */}
        <div className="flex items-center gap-1.5 border border-border px-3 py-1.5 rounded bg-muted/40 font-mono text-[11px]">
          <span
            className={`h-2 w-2 rounded-full ${
              status === "completed"
                ? "bg-emerald-400"
                : status === "processing"
                ? "bg-purple-400 animate-pulse"
                : status === "degraded"
                ? "bg-amber-400"
                : "bg-muted-foreground"
            }`}
          />
          <span className="capitalize">{status}</span>
          {status === "processing" && <span>({progress}%)</span>}
        </div>

        {/* Compare Approaches button */}
        <button
          onClick={onOpenCompare}
          className="flex items-center gap-1.5 border border-purple-500/50 bg-purple-500/10 px-3 py-1.5 rounded font-mono text-purple-300 hover:bg-purple-500 hover:text-white transition-colors"
        >
          <GitCompare className="h-3.5 w-3.5" />
          <span>Compare Approaches</span>
        </button>

        {/* Reset button */}
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 border border-border px-2.5 py-1.5 rounded text-muted-foreground hover:text-foreground transition-colors"
          title="Reset Capture Demo"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
    </header>
  );
};
