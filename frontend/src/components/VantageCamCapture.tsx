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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Upload, AlertCircle, CheckCircle } from "lucide-react";
import type { VantageCamTier } from "@/types/vantagecam";
import { API_BASE_URL } from "@/lib/api";

/**
 * VantageCamCapture Component
 *
 * Analogy: Like a form at a photo lab where you drop off film, choose quality,
 * and get back a processed 3D scene. You enter a name, pick a processing tier,
 * and the backend spins up the 10-stage pipeline.
 */

interface VantageCamCaptureProps {
  onCaptureCreated?: (captureId: string) => void;
}

export function VantageCamCapture({ onCaptureCreated }: VantageCamCaptureProps) {
  const { addCapture, setCurrentCaptureId } = useVantageCamStore();

  const [captureName, setCaptureName] = useState("");
  const [selectedTier, setSelectedTier] = useState<VantageCamTier>("standard");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Tier descriptions and features
  const tierInfo: Record<VantageCamTier, { description: string; duration: string }> = {
    standard: {
      description: "Fast processing, good quality",
      duration: "~2 hours",
    },
    enhanced: {
      description: "Balanced quality and speed, more detail",
      duration: "~4 hours",
    },
    premium: {
      description: "Maximum quality, finest detail",
      duration: "~6+ hours",
    },
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type and size
      if (!file.type.startsWith("video/")) {
        setError("Please select a valid video file");
        setVideoFile(null);
        return;
      }
      if (file.size > 2 * 1024 * 1024 * 1024) {
        setError("Video file must be under 2 GB");
        setVideoFile(null);
        return;
      }
      setVideoFile(file);
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!captureName.trim()) {
      setError("Please enter a capture name");
      return;
    }

    if (!videoFile) {
      setError("Please select a video file");
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Create FormData for multipart upload
      const formData = new FormData();
      formData.append("name", captureName);
      formData.append("tier", selectedTier);
      formData.append("video", videoFile);

      // POST to backend
      const response = await fetch(
        `${API_BASE_URL}/api/vantagecam/captures/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail ||
            errorData.error ||
            `Upload failed: HTTP ${response.status}`
        );
      }

      const data = await response.json();
      console.log("[VantageCamCapture] Capture created:", data);

      // Add to store
      const capture = {
        capture_id: data.capture_id,
        name: data.name,
        tier: data.tier,
        status: data.status,
        created_at: data.created_at,
        updated_at: data.updated_at,
        progress_percent: 0,
        current_stage: null,
      };

      addCapture(capture);
      setCurrentCaptureId(data.capture_id);

      // Success feedback
      setSuccess(
        `Capture "${captureName}" created! Starting pipeline processing...`
      );
      onCaptureCreated?.(data.capture_id);

      // Reset form
      setCaptureName("");
      setVideoFile(null);
      setSelectedTier("standard");
      if (e.target instanceof HTMLFormElement) {
        e.target.reset();
      }
    } catch (err: any) {
      console.error("[VantageCamCapture] Upload failed:", err);
      setError(err.message || "Failed to create capture");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full shadow-sm border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Upload className="h-4 w-4 text-blue-500" />
          <CardTitle className="text-sm font-semibold">New VantageCam Capture</CardTitle>
        </div>
        <CardDescription className="text-xs">
          Upload drone video to start the 10-stage 3D reconstruction pipeline
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Capture Name */}
          <div className="space-y-2">
            <Label htmlFor="capture-name" className="text-xs font-medium">
              Capture Name
            </Label>
            <Input
              id="capture-name"
              placeholder="e.g., Downtown_Site_A"
              value={captureName}
              onChange={(e) => setCaptureName(e.target.value)}
              disabled={isLoading}
              className="h-9 text-xs bg-background/50"
            />
          </div>

          {/* Processing Tier */}
          <div className="space-y-2">
            <Label htmlFor="tier" className="text-xs font-medium">
              Processing Tier
            </Label>
            <Select
              value={selectedTier}
              onValueChange={(value) => setSelectedTier(value as VantageCamTier)}
              disabled={isLoading}
            >
              <SelectTrigger id="tier" className="h-9 text-xs bg-background/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="text-xs">
                {(["standard", "enhanced", "premium"] as VantageCamTier[]).map(
                  (tier) => (
                    <SelectItem key={tier} value={tier}>
                      <div className="flex items-center gap-2">
                        <span className="capitalize font-medium">{tier}</span>
                        <span className="text-muted-foreground text-[11px]">
                          ({tierInfo[tier].duration})
                        </span>
                      </div>
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
            <p className="text-[10px] text-muted-foreground">
              {tierInfo[selectedTier].description}
            </p>
          </div>

          {/* Video File Input */}
          <div className="space-y-2">
            <Label htmlFor="video-file" className="text-xs font-medium">
              Video File
            </Label>
            <div className="flex gap-2 items-center">
              <Input
                id="video-file"
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                disabled={isLoading}
                className="h-9 text-xs file:text-xs file:font-medium bg-background/50"
              />
            </div>
            {videoFile && (
              <p className="text-[10px] text-emerald-500 flex items-center gap-1.5">
                <CheckCircle className="h-3 w-3" />
                {videoFile.name} ({(videoFile.size / (1024 * 1024)).toFixed(1)} MB)
              </p>
            )}
            <p className="text-[10px] text-muted-foreground">
              Max 2 GB. Supported: MP4, MOV, AVI, WebM
            </p>
          </div>

          {/* Tier Details */}
          <div className="bg-muted/40 rounded-md p-3 space-y-2 text-[11px]">
            <div className="font-semibold text-foreground">Pipeline Stages:</div>
            <ul className="space-y-1 text-muted-foreground list-disc list-inside">
              <li>Probe (validate input)</li>
              <li>Frame extraction (video → images)</li>
              <li>Masking (segment foreground)</li>
              <li>SfM (camera poses + sparse points)</li>
              <li>Dense reconstruction (depth maps)</li>
              <li>Mesh extraction (geometry)</li>
              <li>Splat creation (3D Gaussians)</li>
              <li>Georeferencing (scale/alignment)</li>
              <li>Quality gate (metrics check)</li>
              <li>Export (artifacts + database)</li>
            </ul>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive" className="text-xs">
              <AlertCircle className="h-3 w-3" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Success Alert */}
          {success && (
            <Alert className="text-xs border-emerald-500/50 bg-emerald-500/10">
              <CheckCircle className="h-3 w-3 text-emerald-500" />
              <AlertDescription className="text-emerald-600">{success}</AlertDescription>
            </Alert>
          )}

          {/* Submit Button */}
          <Button
            type="submit"
            disabled={isLoading || !captureName.trim() || !videoFile}
            className="w-full h-9 text-xs gap-1.5"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" />
                <span>Create Capture & Start Pipeline</span>
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
