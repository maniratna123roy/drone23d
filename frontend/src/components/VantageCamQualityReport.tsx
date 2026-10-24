import { useMemo } from "react";
import { useVantageCamStore } from "@/store/vantagecamStore";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { AlertCircle, CheckCircle, BarChart3, Gauge, Zap } from "lucide-react";
import type { PipelineStageType } from "@/types/vantagecam";

/**
 * VantageCamQualityReport Component
 *
 * Analogy: Like a final report card showing the quality score, processing time,
 * and detailed metrics for each stage. If something went wrong, shows the error logs.
 */

export function VantageCamQualityReport() {
  const { qualityReport } = useVantageCamStore();

  // Calculate stage-by-stage timing visualization
  const stageTimings = useMemo(() => {
    if (!qualityReport) return [];

    const stages: PipelineStageType[] = [
      "probe",
      "frames",
      "masking",
      "sfm",
      "dense",
      "mesh",
      "splats",
      "georef",
      "quality_gate",
      "export",
    ];

    const timings = stages.map((stage) => ({
      stage,
      duration: qualityReport.stage_durations[stage] || 0,
    }));

    return timings;
  }, [qualityReport]);

  const totalDuration = useMemo(() => {
    if (!qualityReport) return 0;
    return Object.values(qualityReport.stage_durations).reduce((a, b) => a + b, 0);
  }, [qualityReport]);

  // Format milliseconds to readable time
  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  // If no report, show empty state
  if (!qualityReport) {
    return (
      <Card className="w-full shadow-sm border-border/60">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-slate-400" />
            <CardTitle className="text-sm font-semibold">Quality Report</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Pipeline metrics and performance summary
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground text-xs">
            Waiting for pipeline to complete...
          </div>
        </CardContent>
      </Card>
    );
  }

  const isPassed = qualityReport.verdict === "PASS";
  const isFailed = qualityReport.verdict === "FAIL";

  return (
    <Card className="w-full shadow-sm border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-slate-400" />
            <CardTitle className="text-sm font-semibold">Quality Report</CardTitle>
          </div>
          <Badge
            className={`text-xs py-1 px-2 ${
              isPassed
                ? "bg-emerald-500/20 text-emerald-600 border-emerald-500/30"
                : "bg-destructive/20 text-destructive border-destructive/30"
            }`}
            variant="outline"
          >
            {isPassed ? (
              <>
                <CheckCircle className="h-3 w-3 mr-1" />
                PASSED
              </>
            ) : (
              <>
                <AlertCircle className="h-3 w-3 mr-1" />
                FAILED
              </>
            )}
          </Badge>
        </div>
        <CardDescription className="text-xs">
          Total time: {formatTime(qualityReport.total_duration_ms)}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Verdict Summary */}
        <div
          className={`rounded-md border p-3 space-y-2 ${
            isPassed
              ? "border-emerald-500/30 bg-emerald-500/5"
              : "border-destructive/30 bg-destructive/5"
          }`}
        >
          <div className="flex items-center gap-2">
            {isPassed ? (
              <CheckCircle className="h-4 w-4 text-emerald-500" />
            ) : (
              <AlertCircle className="h-4 w-4 text-destructive" />
            )}
            <span className="font-semibold text-sm">
              {isPassed ? "Pipeline Completed Successfully" : "Pipeline Failed"}
            </span>
          </div>
          {isFailed && qualityReport.error_logs && (
            <p className="text-xs text-destructive/80 bg-background/40 rounded p-2 font-mono max-h-24 overflow-y-auto">
              {qualityReport.error_logs}
            </p>
          )}
        </div>

        {/* Key Metrics */}
        {isPassed && (
          <>
            <Separator />
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(qualityReport.metrics).map(([key, value]) => (
                <div
                  key={key}
                  className="rounded-md border border-border/40 bg-background/40 p-2 space-y-1"
                >
                  <div className="text-[10px] text-muted-foreground capitalize font-medium">
                    {key.replace(/_/g, " ")}
                  </div>
                  <div className="text-sm font-semibold text-foreground">
                    {typeof value === "number" ? value.toLocaleString() : String(value)}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Stage Timing Breakdown */}
        {isPassed && stageTimings.some((s) => s.duration > 0) && (
          <>
            <Separator />
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-yellow-500" />
                <span className="font-semibold text-sm">Stage Timing</span>
              </div>

              <div className="space-y-2">
                {stageTimings.map(({ stage, duration }) => {
                  const percent =
                    totalDuration > 0 ? (duration / totalDuration) * 100 : 0;

                  return (
                    <div key={stage} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="capitalize font-medium text-foreground">
                          {stage}
                        </span>
                        <span className="text-muted-foreground font-mono">
                          {formatTime(duration)} ({percent.toFixed(1)}%)
                        </span>
                      </div>
                      <Progress
                        value={percent}
                        className="h-1.5"
                        aria-label={`${stage} stage duration`}
                      />
                    </div>
                  );
                })}
              </div>

              <div className="pt-2 border-t text-xs">
                <div className="flex items-center justify-between font-semibold">
                  <span>Total Pipeline Duration</span>
                  <span>{formatTime(qualityReport.total_duration_ms)}</span>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Artifacts Summary */}
        {qualityReport.artifacts.length > 0 && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-blue-500" />
                <span className="font-semibold text-sm">Output Files</span>
              </div>
              <div className="space-y-1">
                {qualityReport.artifacts.map((artifact) => (
                  <div
                    key={artifact.name}
                    className="flex items-center justify-between text-xs p-1.5 rounded bg-muted/30"
                  >
                    <span className="font-medium text-foreground">
                      {artifact.name}
                    </span>
                    <span className="text-muted-foreground font-mono">
                      {(artifact.size_bytes / (1024 * 1024)).toFixed(2)} MB
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Verdict Icon */}
        <div className="flex justify-center pt-2">
          {isPassed ? (
            <div className="text-emerald-500 flex flex-col items-center gap-1">
              <CheckCircle className="h-8 w-8" />
              <span className="text-xs font-medium">Ready for use</span>
            </div>
          ) : (
            <div className="text-destructive flex flex-col items-center gap-1">
              <AlertCircle className="h-8 w-8" />
              <span className="text-xs font-medium">See logs above</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
