/**
 * VantageCam types: capture, pipeline stages, progress events, artifacts
 */

export type VantageCamTier = "standard" | "enhanced" | "premium";

export type PipelineStageType =
  | "probe"
  | "frames"
  | "masking"
  | "sfm"
  | "dense"
  | "mesh"
  | "splats"
  | "georef"
  | "quality_gate"
  | "export";

export type VantageCamEventType =
  | "stage_start"
  | "stage_progress"
  | "stage_complete"
  | "stage_error"
  | "status_update"
  | "pipeline_complete"
  | "pipeline_failed";

export type PipelineVerdict = "PASS" | "FAIL" | "INCOMPLETE";

/**
 * VantageCam capture metadata
 * Equivalent: `backend/schemas/vantagecam.py::VantageCamCaptureResponse`
 */
export interface VantageCamCapture {
  capture_id: string;
  name: string;
  tier: VantageCamTier;
  status: "queued" | "processing" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  progress_percent: number;
  current_stage: PipelineStageType | null;
}

/**
 * Single stage event from WebSocket
 * Equivalent: JSON messages on /ws/vantagecam/{capture_id}
 */
export interface VantageCamEvent {
  type: VantageCamEventType;
  capture_id: string;
  stage_index?: number;
  stage_name?: PipelineStageType;
  progress?: number; // 0-100
  timestamp: number; // milliseconds since pipeline_start
  duration_ms?: number;
  error_message?: string;
  metadata?: {
    processing_cores?: number;
    memory_mb?: number;
    artifacts?: string[];
    quality_metrics?: Record<string, unknown>;
  };
}

/**
 * Artifact metadata returned after pipeline completion
 */
export interface VantageCamArtifact {
  name: string; // "scene.splat", "labels.npy", "scene_frame.json"
  size_bytes: number;
  created_at: string;
  url: string; // download/preview URL
}

/**
 * Quality report after pipeline completes
 */
export interface VantageCamQualityReport {
  capture_id: string;
  verdict: PipelineVerdict;
  total_duration_ms: number;
  stage_durations: Record<PipelineStageType, number>;
  artifacts: VantageCamArtifact[];
  metrics: {
    gaussian_count?: number;
    splat_size_mb?: number;
    quality_score?: number;
    coverage_percent?: number;
  };
  error_logs?: string;
}

/**
 * UI state for tracking capture in progress
 */
export interface VantageCamUIState {
  captures: VantageCamCapture[];
  currentCaptureId: string | null;
  events: VantageCamEvent[];
  qualityReport: VantageCamQualityReport | null;
  isConnected: boolean;
  error: string | null;
}
