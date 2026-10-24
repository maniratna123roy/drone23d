import { useState, useEffect } from "react";
import { useVantageCamStore } from "@/store/vantagecamStore";
import { useVantageCamWebSocket } from "@/hooks/useVantageCamWebSocket";
import { VantageCamCapture } from "./VantageCamCapture";
import { VantageCamProgress } from "./VantageCamProgress";
import { VantageCamArtifactBrowser } from "./VantageCamArtifactBrowser";
import { VantageCamQualityReport } from "./VantageCamQualityReport";
import {
  VANTAGECAM_DEMO_MODE,
  DEMO_CAPTURES,
  generateDemoQualityReport,
  mockGetCaptures,
} from "@/lib/vantagecamMockApi";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Film,
  Zap,
  History,
  Trash2,
  AlertCircle,
  CheckCircle,
  Clock,
} from "lucide-react";
import type { VantageCamCapture as VantageCamCaptureType } from "@/types/vantagecam";
import { API_BASE_URL } from "@/lib/api";

/**
 * VantageCamPage Component
 *
 * Analogy: The main control center for the VantageCam 3D reconstruction pipeline.
 * Create captures, watch real-time progress, download artifacts, view quality reports.
 * Job queue shows all captures (running/completed/failed).
 */

export function VantageCamPage() {
  const {
    captures,
    currentCaptureId,
    setCurrentCaptureId,
    addCapture,
    updateCapture,
    qualityReport,
    setQualityReport,
  } = useVantageCamStore();

  const [isLoadingCaptures, setIsLoadingCaptures] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Connect WebSocket when current capture changes
  useVantageCamWebSocket({
    captureId: currentCaptureId,
    onQualityReport: (report) => {
      console.log("[VantageCamPage] Quality report received:", report);
      // Update the capture status based on verdict
      if (currentCaptureId) {
        updateCapture(currentCaptureId, {
          status: report.verdict === "PASS" ? "completed" : "failed",
        });
      }
    },
  });

  // In demo mode, load quality report for completed captures
  useEffect(() => {
    if (VANTAGECAM_DEMO_MODE && currentCaptureId && !qualityReport) {
      const capture = captures.find((c) => c.capture_id === currentCaptureId);
      if (capture && capture.status === "completed") {
        const demoReport = generateDemoQualityReport(currentCaptureId);
        setQualityReport(demoReport);
        console.log("[VantageCamPage] Loaded demo quality report for", currentCaptureId);
      }
    }
  }, [currentCaptureId, captures, qualityReport, setQualityReport]);

  // Load existing captures on mount
  useEffect(() => {
    const loadCaptures = async () => {
      setIsLoadingCaptures(true);
      try {
        let capturesData;

        if (VANTAGECAM_DEMO_MODE) {
          // Use demo captures
          capturesData = await mockGetCaptures();
          console.log("[VantageCamPage] Loaded demo captures:", capturesData);

          // Load all demo captures into store
          for (const capture of capturesData) {
            addCapture(capture);

            // If capture is completed, load its quality report
            if (capture.status === "completed") {
              const report = generateDemoQualityReport(capture.capture_id);
              // Store the report in a way accessible to store (you might need to extend store for this)
              console.log(`[VantageCamPage] Generated demo report for ${capture.capture_id}`);
            }
          }

          // Auto-select first demo capture for immediate demo
          if (capturesData.length > 0) {
            setCurrentCaptureId(capturesData[0].capture_id);
          }
        } else {
          // Load from real API
          const response = await fetch(`${API_BASE_URL}/api/vantagecam/captures`, {
            cache: "no-store",
          });
          if (response.ok) {
            const data = await response.json();
            console.log("[VantageCamPage] Loaded captures:", data);
          }
        }
      } catch (err) {
        console.error("[VantageCamPage] Failed to load captures:", err);
      } finally {
        setIsLoadingCaptures(false);
      }
    };

    loadCaptures();
  }, [addCapture, setCurrentCaptureId]);

  const handleDeleteCapture = async (captureId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/vantagecam/captures/${captureId}`,
        {
          method: "DELETE",
        }
      );

      if (response.ok) {
        console.log("[VantageCamPage] Deleted capture:", captureId);
        if (currentCaptureId === captureId) {
          setCurrentCaptureId(null);
        }
        // Remove from captures list
        // In a real app with proper state management, this would be cleaner
      }
    } catch (err) {
      console.error("[VantageCamPage] Failed to delete capture:", err);
    } finally {
      setDeleteConfirm(null);
    }
  };

  const handleCaptureCreated = (captureId: string) => {
    setCurrentCaptureId(captureId);
  };

  const currentCapture = captures.find((c) => c.capture_id === currentCaptureId);

  // Status badge helper
  const getStatusBadge = (capture: VantageCamCaptureType) => {
    const statusClasses: Record<string, { bg: string; icon: React.ReactNode; label: string }> = {
      queued: {
        bg: "bg-slate-500/20 text-slate-600 border-slate-500/30",
        icon: <Clock className="h-3 w-3" />,
        label: "Queued",
      },
      processing: {
        bg: "bg-blue-500/20 text-blue-600 border-blue-500/30",
        icon: <Zap className="h-3 w-3 animate-pulse" />,
        label: "Processing",
      },
      completed: {
        bg: "bg-emerald-500/20 text-emerald-600 border-emerald-500/30",
        icon: <CheckCircle className="h-3 w-3" />,
        label: "Completed",
      },
      failed: {
        bg: "bg-destructive/20 text-destructive border-destructive/30",
        icon: <AlertCircle className="h-3 w-3" />,
        label: "Failed",
      },
    };

    const info = statusClasses[capture.status] || statusClasses.queued;

    return (
      <Badge variant="outline" className={`text-xs py-1 px-2 ${info.bg}`}>
        {info.icon}
        <span className="ml-1">{info.label}</span>
      </Badge>
    );
  };

  return (
    <div className="w-full space-y-6 pb-8">
      {/* Page Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Film className="h-6 w-6 text-blue-500" />
          <h1 className="text-2xl font-bold">VantageCam 3D Reconstruction</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Upload drone video, process through 10-stage pipeline, download 3D assets
        </p>
      </div>

      <Separator />

      {/* Main Layout: Create + Current Capture */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Create Capture Form */}
        <div className="lg:col-span-1">
          <VantageCamCapture onCaptureCreated={handleCaptureCreated} />
        </div>

        {/* Right Column: Current Capture Progress & Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Current Capture Info */}
          {currentCapture ? (
            <Card className="shadow-sm border-border/60">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-sm font-semibold">
                      {currentCapture.name}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {currentCapture.capture_id}
                    </CardDescription>
                  </div>
                  {getStatusBadge(currentCapture)}
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-xs">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <span className="text-muted-foreground">Tier:</span>
                    <div className="font-semibold capitalize">{currentCapture.tier}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Created:</span>
                    <div className="font-mono text-[10px]">
                      {new Date(currentCapture.created_at).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Progress:</span>
                    <div className="font-semibold">{currentCapture.progress_percent}%</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="shadow-sm border-border/60 bg-background/40">
              <CardContent className="pt-6">
                <div className="text-center py-8 text-muted-foreground text-xs">
                  Select or create a capture to view progress and results
                </div>
              </CardContent>
            </Card>
          )}

          {/* Progress Viewer */}
          {currentCaptureId && <VantageCamProgress captureId={currentCaptureId} />}

          {/* Quality Report */}
          {currentCaptureId && qualityReport && (
            <VantageCamQualityReport />
          )}

          {/* Artifact Browser */}
          {currentCaptureId && (
            <VantageCamArtifactBrowser captureId={currentCaptureId} />
          )}
        </div>
      </div>

      {/* Job Queue / Capture History */}
      <Separator className="my-8" />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-slate-400" />
            <h2 className="text-lg font-semibold">Capture History</h2>
          </div>
          <span className="text-xs text-muted-foreground">
            {captures.length} capture{captures.length !== 1 ? "s" : ""}
          </span>
        </div>

        {captures.length === 0 ? (
          <Card className="shadow-sm border-border/60 bg-background/40">
            <CardContent className="pt-6">
              <div className="text-center py-8 text-muted-foreground text-xs">
                No captures yet. Create one above to get started.
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-2">
            {captures.map((capture) => (
              <Card
                key={capture.capture_id}
                className={`shadow-sm border-border/60 cursor-pointer transition-all hover:border-border/80 ${
                  currentCaptureId === capture.capture_id
                    ? "ring-2 ring-blue-500/50"
                    : ""
                }`}
                onClick={() => setCurrentCaptureId(capture.capture_id)}
              >
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between gap-3">
                    {/* Capture Info */}
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-foreground truncate">
                          {capture.name}
                        </span>
                        {getStatusBadge(capture)}
                      </div>
                      <div className="text-[10px] text-muted-foreground space-x-2 flex flex-wrap">
                        <span className="capitalize">{capture.tier}</span>
                        <span>•</span>
                        <span>
                          {new Date(capture.created_at).toLocaleString()}
                        </span>
                        <span>•</span>
                        <span className="font-mono">{capture.progress_percent}%</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-1 flex-shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteConfirm(capture.capture_id);
                        }}
                        className="h-8 px-2"
                        title="Delete capture"
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive/60 hover:text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirm && (
        <Card className="shadow-lg border-destructive/50 bg-destructive/5 fixed bottom-4 right-4 w-96 z-50">
          <CardHeader>
            <CardTitle className="text-sm">Delete Capture?</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted-foreground">
              This will permanently delete the capture and all associated files.
            </p>
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeleteConfirm(null)}
                className="text-xs h-8"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleDeleteCapture(deleteConfirm)}
                className="text-xs h-8"
              >
                Delete
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
