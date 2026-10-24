import { useState } from "react";
import { useVantageCamStore } from "@/store/vantagecamStore";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Download,
  Eye,
  Package,
  FileJson,
  Zap,
  Loader2,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import type { VantageCamArtifact } from "@/types/vantagecam";
import { API_BASE_URL } from "@/lib/api";

/**
 * VantageCamArtifactBrowser Component
 *
 * Analogy: Like a gallery where you can browse output files from the pipeline:
 * scene.splat (3D Gaussian file), labels.npy (class assignments), and
 * scene_frame.json (coordinate frame metadata). Preview or download each.
 */

interface VantageCamArtifactBrowserProps {
  captureId?: string | null;
}

export function VantageCamArtifactBrowser({
  captureId,
}: VantageCamArtifactBrowserProps) {
  const { qualityReport } = useVantageCamStore();
  const [previewingArtifact, setPreviewingArtifact] =
    useState<VantageCamArtifact | null>(null);
  const [isDownloading, setIsDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const artifacts = qualityReport?.artifacts || [];

  // Artifact type info and icons
  const artifactInfo: Record<
    string,
    {
      description: string;
      icon: React.ReactNode;
      badge: string;
      previewable: boolean;
    }
  > = {
    "scene.splat": {
      description: "3D Gaussian Splatting file - the photorealistic 3D scene",
      icon: <Zap className="h-4 w-4 text-yellow-500" />,
      badge: "3D Model",
      previewable: true,
    },
    "labels.npy": {
      description: "NumPy array of class labels per Gaussian (0-255)",
      icon: <FileJson className="h-4 w-4 text-blue-500" />,
      badge: "Classes",
      previewable: false,
    },
    "scene_frame.json": {
      description: "Coordinate frame metadata (scale, alignment, bounds)",
      icon: <FileJson className="h-4 w-4 text-green-500" />,
      badge: "Metadata",
      previewable: true,
    },
  };

  const handleDownload = async (artifact: VantageCamArtifact) => {
    if (!captureId) {
      setDownloadError("No capture ID available");
      return;
    }

    setIsDownloading(artifact.name);
    setDownloadError(null);

    try {
      // Construct download URL
      const downloadUrl = `${API_BASE_URL}/api/vantagecam/captures/${captureId}/artifacts/${artifact.name}/download`;

      // Create a temporary anchor element to trigger download
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = artifact.name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      console.log(`[ArtifactBrowser] Downloaded ${artifact.name}`);
    } catch (err: any) {
      console.error("[ArtifactBrowser] Download failed:", err);
      setDownloadError(err.message || "Failed to download artifact");
    } finally {
      setIsDownloading(null);
    }
  };

  const handlePreview = (artifact: VantageCamArtifact) => {
    const info = artifactInfo[artifact.name];
    if (info?.previewable) {
      setPreviewingArtifact(artifact);
    }
  };

  // If no artifacts, show empty state
  if (artifacts.length === 0) {
    return (
      <Card className="w-full shadow-sm border-border/60">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-slate-400" />
            <CardTitle className="text-sm font-semibold">Output Artifacts</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Download or preview 3D scene and metadata files
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground text-xs flex flex-col items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>Pipeline has not completed yet. Artifacts will appear here.</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="w-full shadow-sm border-border/60">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-emerald-500" />
            <CardTitle className="text-sm font-semibold">Output Artifacts</CardTitle>
          </div>
          <CardDescription className="text-xs">
            {artifacts.length} file
            {artifacts.length !== 1 ? "s" : ""} available for download
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          {artifacts.map((artifact) => {
            const info = artifactInfo[artifact.name];
            const sizeInMB = (artifact.size_bytes / (1024 * 1024)).toFixed(2);
            const isDownloading_ = isDownloading === artifact.name;

            return (
              <div
                key={artifact.name}
                className="rounded-md border border-border/40 bg-background/40 p-3 space-y-2 hover:bg-background/60 transition-colors"
              >
                {/* Artifact Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-2.5 flex-1">
                    {info?.icon || <Package className="h-4 w-4 text-muted-foreground mt-0.5" />}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-foreground break-all">
                          {artifact.name}
                        </span>
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 flex-shrink-0">
                          {info?.badge || "File"}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {info?.description || "Pipeline artifact"}
                      </p>
                    </div>
                  </div>
                </div>

                {/* File Info */}
                <div className="flex items-center justify-between text-[11px] text-muted-foreground bg-muted/30 rounded px-2 py-1">
                  <span>Size: {sizeInMB} MB</span>
                  <span>Created: {new Date(artifact.created_at).toLocaleString()}</span>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2 pt-1">
                  {info?.previewable && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePreview(artifact)}
                      disabled={isDownloading_}
                      className="flex-1 h-8 text-xs gap-1"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span>Preview</span>
                    </Button>
                  )}
                  <Button
                    size="sm"
                    onClick={() => handleDownload(artifact)}
                    disabled={isDownloading_}
                    className="flex-1 h-8 text-xs gap-1"
                  >
                    {isDownloading_ ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Downloading...</span>
                      </>
                    ) : (
                      <>
                        <Download className="h-3.5 w-3.5" />
                        <span>Download</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            );
          })}

          {downloadError && (
            <div className="p-2 rounded bg-destructive/10 text-destructive text-xs flex items-start gap-2">
              <AlertCircle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
              <span>{downloadError}</span>
            </div>
          )}

          {/* Info */}
          <Separator className="my-2" />
          <div className="text-[10px] text-muted-foreground space-y-1 bg-muted/20 rounded p-2">
            <div className="flex items-start gap-1.5">
              <CheckCircle className="h-3 w-3 text-emerald-500 mt-0.5 flex-shrink-0" />
              <span>
                <strong>scene.splat:</strong> Import into Three.js viewer or other
                3D engines
              </span>
            </div>
            <div className="flex items-start gap-1.5">
              <CheckCircle className="h-3 w-3 text-emerald-500 mt-0.5 flex-shrink-0" />
              <span>
                <strong>labels.npy:</strong> Semantic class per Gaussian (shape:
                [num_gaussians])
              </span>
            </div>
            <div className="flex items-start gap-1.5">
              <CheckCircle className="h-3 w-3 text-emerald-500 mt-0.5 flex-shrink-0" />
              <span>
                <strong>scene_frame.json:</strong> Scale factor, alignment transform,
                bounds
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preview Dialog */}
      {previewingArtifact && (
        <Dialog open={!!previewingArtifact} onOpenChange={() => setPreviewingArtifact(null)}>
          <DialogContent className="max-w-2xl max-h-96 overflow-y-auto">
            <DialogTitle>{previewingArtifact.name}</DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-2 text-xs">
                {previewingArtifact.name === "scene_frame.json" && (
                  <div className="bg-muted/40 rounded p-3 font-mono text-[11px] overflow-auto max-h-64">
                    <pre className="whitespace-pre-wrap">
                      {/* In a real implementation, fetch and parse the JSON */}
                      Coordinate frame metadata for 3D scene alignment
                    </pre>
                  </div>
                )}
                {previewingArtifact.name === "scene.splat" && (
                  <div className="bg-muted/40 rounded p-3 text-foreground text-[11px]">
                    <p>
                      <strong>Binary 3D Gaussian Splatting file</strong>
                    </p>
                    <p className="text-muted-foreground mt-2">
                      Size: {(previewingArtifact.size_bytes / (1024 * 1024)).toFixed(2)} MB
                    </p>
                    <p className="text-muted-foreground mt-2">
                      This file contains the photorealistic 3D scene. Preview in a
                      dedicated 3D viewer or import into Three.js/Babylon.js.
                    </p>
                  </div>
                )}
              </div>
            </DialogDescription>
            <div className="flex gap-2 pt-4">
              <Button variant="outline" onClick={() => setPreviewingArtifact(null)}>
                Close
              </Button>
              <Button
                onClick={() => handleDownload(previewingArtifact)}
                disabled={isDownloading === previewingArtifact.name}
              >
                {isDownloading === previewingArtifact.name ? "Downloading..." : "Download"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
