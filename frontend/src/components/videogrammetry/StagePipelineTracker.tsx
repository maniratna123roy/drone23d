import React from "react";
import { CheckCircle2, Clock, AlertTriangle, Loader2 } from "lucide-react";

export interface StageData {
  stage: string;
  title: string;
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  duration_s?: number;
  metrics?: Record<string, any>;
  error?: string;
}

interface StagePipelineTrackerProps {
  stages: StageData[];
  currentStage: string | null;
  attempt: number;
}

export const StagePipelineTracker: React.FC<StagePipelineTrackerProps> = ({
  stages,
  currentStage,
  attempt,
}) => {
  return (
    <div className="rounded-lg border border-border/80 bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
            2. State Machine Pipeline Tracker (8 Stages)
          </h2>
          <p className="text-xs text-muted-foreground">
            Idempotent content-addressed stages with checkpointing and automatic redo ladder.
          </p>
        </div>
        {attempt > 1 && (
          <span className="text-xs font-mono px-2.5 py-1 rounded border border-purple-500/40 bg-purple-950/60 text-purple-300">
            QA Retry Ladder: Attempt #{attempt}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-9 gap-2">
        {stages.map((st, idx) => {
          const isRunning = st.status === "running";
          const isDone = st.status === "completed";
          const isFailed = st.status === "failed";
          const isSkipped = st.status === "skipped";

          return (
            <div
              key={st.stage}
              className={`flex flex-col p-2.5 rounded border text-xs transition-all ${
                isRunning
                  ? "border-purple-500 bg-purple-500/10 shadow-md shadow-purple-500/10"
                  : isDone
                  ? "border-emerald-500/40 bg-emerald-950/20 text-foreground"
                  : isFailed
                  ? "border-red-500/50 bg-red-950/20"
                  : isSkipped
                  ? "border-border/30 bg-muted/10 opacity-50"
                  : "border-border/40 bg-muted/20 opacity-70"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5 font-mono text-[10px]">
                <span className="text-muted-foreground">0{idx}</span>
                {isRunning && <Loader2 className="h-3 w-3 animate-spin text-purple-400" />}
                {isDone && <CheckCircle2 className="h-3 w-3 text-emerald-400" />}
                {isFailed && <AlertTriangle className="h-3 w-3 text-red-400" />}
                {st.status === "pending" && <Clock className="h-3 w-3 text-muted-foreground" />}
              </div>

              <div className="font-medium text-[11px] line-clamp-2 leading-tight mb-2">
                {st.title.replace(/^Stage \d+: /, "")}
              </div>

              <div className="mt-auto pt-1.5 border-t border-border/30 font-mono text-[10px] text-muted-foreground flex justify-between items-center">
                <span className="capitalize">{st.status}</span>
                {st.duration_s !== undefined && st.duration_s > 0 && (
                  <span>{st.duration_s.toFixed(1)}s</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
