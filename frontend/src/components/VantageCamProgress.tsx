import { useEffect, useMemo } from "react";
import { useVantageCamStore } from "@/store/vantagecamStore";
import { useVantageCamWebSocket } from "@/hooks/useVantageCamWebSocket";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Play,
  CheckCircle,
  AlertCircle,
  Zap,
  Clock,
  Gauge,
} from "lucide-react";
import type { VantageCamEvent, PipelineStageType } from "@/types/vantagecam";

/**
 * VantageCamProgress Component
 *
 * Analogy: Like a dashboard showing each stage of a pipeline—when it starts,
 * its progress (25%, 50%, 75%), and when it completes. All 10 stages stream
 * in real-time via WebSocket.
 */

interface VantageCamProgressProps {
  captureId?: string | null;
}

export function VantageCamProgress({ captureId }: VantageCamProgressProps) {
  const { events, getCurrentProgress } = useVantageCamStore();
  const { isConnected } = useVantageCamWebSocket({ captureId });

  // Group events by stage
  const stageEvents = useMemo(() => {
    const stages: Record<PipelineStageType, VantageCamEvent[]> = {
      probe: [],
      frames: [],
      masking: [],
      sfm: [],
      dense: [],
      mesh: [],
      splats: [],
      georef: [],
      quality_gate: [],
      export: [],
    };

    for (const event of events) {
      if (event.stage_name && event.stage_name in stages) {
        stages[event.stage_name].push(event);
      }
    }

    return stages;
  }, [events]);

  // Calculate overall progress
  const overallProgress = getCurrentProgress();

  // Find pipeline status
  const isPipelineComplete = events.some((e) => e.type === "pipeline_complete");
  const isPipelineFailed = events.some((e) => e.type === "pipeline_failed");
  const isPipelineRunning = !isPipelineComplete && !isPipelineFailed && events.length > 0;

  // Get total duration if available
  const totalDuration = useMemo(() => {
    const completeEvent = events.find((e) => e.type === "pipeline_complete");
    if (completeEvent?.timestamp) {
      return completeEvent.timestamp;
    }
    return 0;
  }, [events]);

  // Format milliseconds to readable time
  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

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

  const getStageStatus = (stageName: PipelineStageType) => {
    const stageEventList = stageEvents[stageName];
    if (stageEventList.length === 0) return "pending";

    const hasComplete = stageEventList.some((e) => e.type === "stage_complete");
    const hasError = stageEventList.some((e) => e.type === "stage_error");
    const hasStart = stageEventList.some((e) => e.type === "stage_start");

    if (hasError) return "error";
    if (hasComplete) return "complete";
    if (hasStart) return "running";
    return "pending";
  };

  const getStageProgress = (stageName: PipelineStageType) => {
    const stageEventList = stageEvents[stageName];
    const progressEvent = stageEventList
      .reverse()
      .find((e) => e.type === "stage_progress" || e.type === "stage_complete");
    return progressEvent?.progress || 0;
  };

  const getStageDuration = (stageName: PipelineStageType) => {
    const completeEvent = stageEvents[stageName].find(
      (e) => e.type === "stage_complete"
    );
    return completeEvent?.duration_ms || 0;
  };

  // If no events yet, show empty state
  if (events.length === 0) {
    return (
      <Card className="w-full shadow-sm border-border/60">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-slate-400" />
            <CardTitle className="text-sm font-semibold">Pipeline Progress</CardTitle>
          </div>
          <CardDescription className="text-xs">
            {isConnected
              ? "Waiting for pipeline to start..."
              : "Not connected to pipeline stream"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground text-xs">
            {isConnected
              ? "Select a capture or create a new one to begin processing"
              : "Connecting to pipeline stream..."}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full shadow-sm border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-yellow-500" />
            <CardTitle className="text-sm font-semibold">Pipeline Progress</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {isPipelineComplete && (
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 text-[10px]">
                ✓ Complete
              </Badge>
            )}
            {isPipelineFailed && (
              <Badge variant="destructive" className="text-[10px]">
                ✗ Failed
              </Badge>
            )}
            {isPipelineRunning && (
              <Badge className="bg-blue-500/20 text-blue-600 border-blue-500/30 text-[10px]">
                ⚡ Running
              </Badge>
            )}
          </div>
        </div>
        <CardDescription className="text-xs">
          {isPipelineComplete
            ? `Completed in ${formatTime(totalDuration)}`
            : isPipelineFailed
              ? "Pipeline encountered an error"
              : `Running • ${overallProgress}% complete`}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Overall Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-foreground">Overall Progress</span>
            <span className="text-xs text-muted-foreground font-mono">
              {overallProgress}%
            </span>
          </div>
          <Progress value={overallProgress} className="h-2" />
        </div>

        <Separator className="my-3" />

        {/* Stage Grid */}
        <div className="grid grid-cols-2 gap-2">
          {stages.map((stageName) => {
            const status = getStageStatus(stageName);
            const progress = getStageProgress(stageName);
            const duration = getStageDuration(stageName);

            const statusColors = {
              pending: "border-border/40 bg-background/40",
              running: "border-blue-500/40 bg-blue-500/5",
              complete: "border-emerald-500/40 bg-emerald-500/5",
              error: "border-destructive/40 bg-destructive/5",
            };

            const statusIcons = {
              pending: <div className="h-3 w-3 rounded-full border border-border/60" />,
              running: (
                <div className="h-3 w-3 rounded-full border-2 border-transparent border-t-blue-500 border-r-blue-500 animate-spin" />
              ),
              complete: <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />,
              error: <AlertCircle className="h-3.5 w-3.5 text-destructive" />,
            };

            return (
              <div
                key={stageName}
                className={`rounded-md border p-2.5 space-y-1.5 text-xs transition-all ${statusColors[status]}`}
              >
                {/* Stage Name & Icon */}
                <div className="flex items-center gap-1.5 justify-between">
                  <span className="font-medium text-foreground capitalize truncate">
                    {stageName}
                  </span>
                  {statusIcons[status]}
                </div>

                {/* Progress */}
                {status !== "pending" && (
                  <>
                    <div className="w-full bg-background/60 rounded h-1.5">
                      <div
                        className={`h-full rounded transition-all ${
                          status === "error"
                            ? "bg-destructive/60"
                            : status === "complete"
                              ? "bg-emerald-500/60"
                              : "bg-blue-500/60"
                        }`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground">
                        {progress}%
                      </span>
                      {duration > 0 && (
                        <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-0.5">
                          <Clock className="h-2.5 w-2.5" />
                          {formatTime(duration)}
                        </span>
                      )}
                    </div>
                  </>
                )}

                {/* Error message */}
                {status === "error" && (
                  <div className="text-[9px] text-destructive line-clamp-2">
                    {events.find(
                      (e) =>
                        e.stage_name === stageName && e.type === "stage_error"
                    )?.error_message || "Unknown error"}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Event Feed (Recent events) */}
        {events.length > 0 && (
          <>
            <Separator className="my-3" />
            <details className="text-xs bg-muted/40 rounded p-2 group">
              <summary className="cursor-pointer font-medium text-muted-foreground flex items-center gap-1.5 select-none">
                <Play className="h-3 w-3 group-open:hidden" />
                <span>Live Event Feed ({events.length})</span>
              </summary>
              <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
                {events
                  .slice()
                  .reverse()
                  .map((event, idx) => (
                    <div
                      key={idx}
                      className="text-[10px] text-muted-foreground font-mono p-1 bg-background/60 rounded border border-border/40 line-clamp-1"
                      title={`${event.type} @ ${event.timestamp}ms`}
                    >
                      <span className="text-yellow-500">
                        {event.type}
                      </span>
                      {event.stage_name && (
                        <span className="ml-1 text-blue-400">{event.stage_name}</span>
                      )}
                      {event.progress !== undefined && (
                        <span className="ml-1 text-emerald-400">{event.progress}%</span>
                      )}
                      {event.error_message && (
                        <span className="ml-1 text-destructive">
                          {event.error_message}
                        </span>
                      )}
                    </div>
                  ))}
              </div>
            </details>
          </>
        )}

        {/* Status summary */}
        <div className="text-[10px] text-muted-foreground flex items-center justify-between pt-2">
          <span>
            WebSocket:{" "}
            {isConnected ? (
              <span className="text-emerald-500">● Connected</span>
            ) : (
              <span className="text-amber-500">○ Disconnected</span>
            )}
          </span>
          <span>Events: {events.length}</span>
        </div>
      </CardContent>
    </Card>
  );
}
