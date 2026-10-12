/** Classification and metre calibration are separate scene capabilities. */
export type SourceVector3 = [number, number, number];

export interface VerifiedSceneManifest {
  schema_version: 1;
  job_id: string;
  source_job_id?: string;
  version: string;
  source_name: string;
  created_at: string;
  splat_url: string;
  classes_url: string;
  gaussian_count: number;
  coordinate_frame: "COLMAP_PHASE_A" | "ALIGNED_GROUND" | "SCENE_METRIC";
  scale_status: "RELATIVE_UNCALIBRATED" | "METRIC_APPROXIMATE" | "CALIBRATED";
  semantics: "UNKNOWN" | "EXTRACTED_STRUCTURES" | "KNOWN" | "CLASSIFIED_MULTIVIEW";
  classification?: {
    method?: string;
    class_counts?: Record<string, number>;
    classified_fraction?: number;
    views?: number;
    attributes?: any;
    classes_available?: string[];
  };
  capabilities: { queries: boolean; edits: boolean };
  bounds: { min: SourceVector3; max: SourceVector3 };
  camera: {
    position: SourceVector3;
    target: SourceVector3;
    up: SourceVector3;
    fov_y_degrees: number;
    near: number;
    far: number;
  };
  quality: Record<string, unknown>;
}

export type VerifiedSceneResponse =
  | { status: "empty"; manifest: null }
  | { status: "ready"; manifest: VerifiedSceneManifest };

export interface PipelineStatus {
  job_id: string | null;
  status: "idle" | "processing" | "completed" | "error";
  step: string;
  progress: number;
  details: Record<string, unknown>;
  error: string | null;
}

export type LayerId =
  | "buildings"
  | "roads"
  | "terrain"
  | "vegetation"
  | "infrastructure";

export interface Layer {
  id: LayerId;
  label: string;
  count: number;
  enabled: boolean;
}

export interface Project {
  id: string;
  name: string;
  location: string;
  coordinates: { lat: number; lng: number };
  createdAt: string;
  missionIds: string[];
}

export interface Mission {
  id: string;
  projectId: string;
  label: string;
  durationSec: number;
  altitudeM: number;
  frames: number;
  capturedAt: string;
}

export type ProcessingStage =
  | "capture"
  | "reconstruction"
  | "semantics"
  | "intelligence";

export interface ProcessingJob {
  id: string;
  missionId: string;
  stage: ProcessingStage;
  progress: number;
  status: "queued" | "running" | "complete";
  metrics: { label: string; value: string }[];
}

export interface SpatialObject {
  id: string;
  label: string;
  layer: LayerId;
  /** grid position in scene units */
  x: number;
  z: number;
  width: number;
  depth: number;
  /** metres */
  height: number;
  elevationM: number;
  areaM2: number;
  region?: string | undefined;
  footprint?: any;
  splatBbox?: {
    min_x: number;
    min_y: number;
    min_z: number;
    max_x: number;
    max_y: number;
    max_z: number;
  } | undefined;
  originalHeightM?: number | undefined;
  version?: number | undefined;
}

export interface Scene {
  id: string;
  projectId: string;
  boundsM: [number, number];
  pointCount: number;
  objects: SpatialObject[];
  layers: Layer[];
}

export interface SpatialQuery {
  id: string;
  prompt: string;
  /** typed result headline, e.g. "07 BUILDINGS FOUND" */
  resultLabel: string;
  resultValue: string;
  matchedObjectIds: string[];
}

export interface SpatialEdit {
  id: string;
  command: string;
  targetObjectIds: string[];
  operation: "extrude" | "raise-terrain";
  deltaM: number;
  status: { objects: number; delta: string; state: string };
}

export interface EditPreviewDelta {
  object_id: number;
  current_height_m: number;
  new_height_m: number;
  delta_height_m: number;
  footprint?: any;
  splat_bbox?: {
    min_x: number;
    min_y: number;
    min_z: number;
    max_x: number;
    max_y: number;
    max_z: number;
  };
}

export interface GhostObject {
  id: string;
  originalHeight: number;
  newHeight: number;
  deltaHeight: number;
  elevationM: number;
  x: number;
  z: number;
  width: number;
  depth: number;
  footprint?: any;
}
