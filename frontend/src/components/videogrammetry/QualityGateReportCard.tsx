import React from "react";
import { ShieldCheck, AlertCircle, RefreshCw, CheckCircle2, Award } from "lucide-react";

export interface QualityReportData {
  job_id: string;
  attempt: number;
  metrics: {
    registered_frames_ratio: number;
    mean_reprojection_error_px: number;
    sparse_points_count: number;
    dense_points_count: number;
    mesh_triangles_count: number;
    mesh_hole_area_ratio: number;
    held_out_ssim: number;
    outlier_geometry_ratio: number;
    ground_sample_distance_cm: number;
    scale_accuracy_note: string;
  };
  verdict: "pass" | "retry" | "degraded" | "fail";
  retry_strategy?: string;
  evaluated_at: string;
}

interface QualityGateReportCardProps {
  report: QualityReportData | null;
}

export const QualityGateReportCard: React.FC<QualityGateReportCardProps> = ({ report }) => {
  if (!report) {
    return (
      <div className="rounded-lg border border-border/80 bg-card p-5 text-center text-xs text-muted-foreground">
        Quality Gate report will be evaluated after Stage 6 meshing and dense reconstruction.
      </div>
    );
  }

  const { metrics, verdict, attempt, retry_strategy } = report;

  return (
    <div className="rounded-lg border border-border/80 bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Award className="h-5 w-5 text-purple-400" />
          <div>
            <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              AI Quality Gate & Automated Redo Verdict
            </h3>
            <p className="text-xs text-muted-foreground">
              Evaluated on Attempt #{attempt} against strict photogrammetric confidence criteria.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {verdict === "pass" && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-500/40">
              <CheckCircle2 className="h-4 w-4" />
              VERDICT: PASS
            </span>
          )}
          {verdict === "retry" && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-purple-950/80 text-purple-300 border border-purple-500/40">
              <RefreshCw className="h-4 w-4 animate-spin" />
              VERDICT: RETRY LADDER
            </span>
          )}
          {verdict === "degraded" && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-amber-950/80 text-amber-300 border border-amber-500/40">
              <AlertCircle className="h-4 w-4" />
              VERDICT: DEGRADED (SHIPPED)
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs mb-4">
        {/* Metric 1: Registration Ratio */}
        <div className="p-3 rounded border border-border/60 bg-muted/20">
          <div className="text-[10px] text-muted-foreground">Registered Frames</div>
          <div className="text-base font-bold text-foreground mt-0.5">
            {(metrics.registered_frames_ratio * 100).toFixed(1)}%
          </div>
          <div className="text-[9px] text-emerald-400 mt-1">Goal: ≥ 85.0%</div>
        </div>

        {/* Metric 2: Reprojection Error */}
        <div className="p-3 rounded border border-border/60 bg-muted/20">
          <div className="text-[10px] text-muted-foreground">Reprojection Error</div>
          <div className="text-base font-bold text-foreground mt-0.5">
            {metrics.mean_reprojection_error_px.toFixed(2)} px
          </div>
          <div className="text-[9px] text-emerald-400 mt-1">Goal: ≤ 1.00 px</div>
        </div>

        {/* Metric 3: Held-Out View SSIM */}
        <div className="p-3 rounded border border-border/60 bg-muted/20">
          <div className="text-[10px] text-muted-foreground">Held-out View SSIM</div>
          <div className="text-base font-bold text-foreground mt-0.5">
            {metrics.held_out_ssim.toFixed(2)}
          </div>
          <div className="text-[9px] text-emerald-400 mt-1">Goal: ≥ 0.70 SSIM</div>
        </div>

        {/* Metric 4: Mesh Hole Area */}
        <div className="p-3 rounded border border-border/60 bg-muted/20">
          <div className="text-[10px] text-muted-foreground">Mesh Hole Area</div>
          <div className="text-base font-bold text-foreground mt-0.5">
            {(metrics.mesh_hole_area_ratio * 100).toFixed(2)}%
          </div>
          <div className="text-[9px] text-emerald-400 mt-1">Goal: &lt; 2.0%</div>
        </div>
      </div>

      <div className="p-3 rounded border border-border/40 bg-muted/10 text-xs">
        <div className="flex justify-between items-center text-[11px] font-mono text-muted-foreground">
          <span>Sparse Points: <strong className="text-foreground">{metrics.sparse_points_count.toLocaleString()}</strong></span>
          <span>Dense MVS Cloud: <strong className="text-purple-300">{metrics.dense_points_count.toLocaleString()} pts</strong></span>
          <span>Mesh Triangles: <strong className="text-foreground">{metrics.mesh_triangles_count.toLocaleString()}</strong></span>
          <span>GSD: <strong className="text-emerald-400">{metrics.ground_sample_distance_cm} cm/px</strong></span>
        </div>
        {retry_strategy && (
          <div className="mt-2 pt-2 border-t border-border/40 text-[11px] text-purple-300">
            <strong>Active Strategy:</strong> {retry_strategy}
          </div>
        )}
      </div>
    </div>
  );
};
