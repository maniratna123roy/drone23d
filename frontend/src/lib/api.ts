import type {
  Mission,
  ProcessingJob,
  Project,
  Scene,
  SpatialEdit,
  SpatialObject,
  SpatialQuery,
} from "@/types/spatial";
import * as mockApi from "./mockApi";
import { createVerifiedPipelineApi } from "./verifiedPipeline";

export const API_BASE_URL =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) || "http://127.0.0.1:8000";

/** The verified /demo flow never uses the showcase mocks or legacy DB endpoints. */
export const verifiedPipelineApi = createVerifiedPipelineApi(API_BASE_URL);

export interface BackendStructure {
  id: number;
  project_id: number;
  class_name: string;
  label?: string | null;
  footprint: any;
  height_m: number;
  width_m?: number | null;
  depth_m?: number | null;
  area_m2: number;
  volume_m3?: number | null;
  elevation_m?: number | null;
  region: string | null;
  splat_bbox: {
    min_x: number;
    min_y: number;
    min_z: number;
    max_x: number;
    max_y: number;
    max_z: number;
  } | null;
  original_height_m: number | null;
  version: number;
}

export interface ClassifiedAttributesSummary {
  structures_count: number;
  roads_count: number;
  vegetation_count: number;
  terrain_count: number;
  structures_metrics: {
    max_height_m: number;
    avg_height_m: number;
    total_footprint_m2: number;
    total_volume_m3: number;
  };
  roads_metrics: {
    corridor_length_m: number;
    avg_width_m: number;
    total_area_m2: number;
  };
  vegetation_metrics: {
    max_canopy_height_m: number;
    total_area_m2: number;
  };
  terrain_metrics: {
    total_area_m2: number;
  };
}

export interface ClassifiedAttributes {
  summary: ClassifiedAttributesSummary;
  structures: any[];
  roads: any[];
  vegetation: any[];
  terrain: any[];
}

export interface QueryMetrics {
  count: number;
  avg_height_m: number;
  total_area_m2: number;
  min_height_m: number;
  max_height_m: number;
}

export interface QueryResponse {
  status: string;
  query: string;
  matched_ids: number[];
  objects: BackendStructure[];
  metrics: QueryMetrics | null;
  intent: any | null;
  sql: string | null;
  message?: string;
  latency_ms: number;
}

export function transformStructureToSpatialObject(s: BackendStructure): SpatialObject {
  const bbox = s.splat_bbox;
  let width = s.width_m ?? 10;
  let depth = s.depth_m ?? 10;
  let x = 0;
  let z = 0;
  let elevationM = s.elevation_m ?? 0;

  if (bbox) {
    if (!s.width_m) width = Math.max(1, bbox.max_x - bbox.min_x);
    if (!s.depth_m) depth = Math.max(1, bbox.max_y - bbox.min_y);
    x = (bbox.min_x + bbox.max_x) / 2;
    z = (bbox.min_y + bbox.max_y) / 2;
    if (s.elevation_m === undefined || s.elevation_m === null) elevationM = bbox.min_z;
  }

  return {
    id: String(s.id),
    label: s.label || `Structure #${s.id}${s.region ? ` (${s.region.toUpperCase()})` : ""}`,
    layer: "buildings",
    x,
    z,
    width,
    depth,
    height: s.height_m,
    elevationM,
    areaM2: s.area_m2,
    region: s.region ?? undefined,
    footprint: s.footprint,
    splatBbox: bbox ?? undefined,
    originalHeightM: s.original_height_m ?? s.height_m,
    version: s.version,
  };
}

export const api = {
  getProject: (): Promise<Project> => mockApi.getProject(),
  getMissions: (): Promise<Mission[]> => mockApi.getMissions(),
  getPipeline: (): Promise<ProcessingJob[]> => mockApi.getPipeline(),
  getScene: (): Promise<Scene> => mockApi.getScene(),
  getQueries: (): Promise<SpatialQuery[]> => mockApi.getQueries(),
  getEdits: (): Promise<SpatialEdit[]> => mockApi.getEdits(),

  // Live Backend Endpoints
  fetchBackendStructures: async (): Promise<SpatialObject[]> => {
    const res = await fetch(`${API_BASE_URL}/api/objects/structures`);
    if (!res.ok) throw new Error(`Failed to fetch structures: ${res.statusText}`);
    const data: BackendStructure[] = await res.json();
    return data.map(transformStructureToSpatialObject);
  },

  fetchClassifiedAttributes: async (): Promise<ClassifiedAttributes> => {
    const res = await fetch(`${API_BASE_URL}/api/objects/classified-attributes`);
    if (!res.ok) throw new Error(`Failed to fetch classified attributes: ${res.statusText}`);
    return await res.json();
  },

  fetchBackendProject: async (): Promise<any> => {
    const res = await fetch(`${API_BASE_URL}/api/objects/project`);
    if (!res.ok) throw new Error(`Failed to fetch project: ${res.statusText}`);
    return await res.json();
  },

  submitQuery: async (text: string): Promise<QueryResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`Query failed: ${res.statusText}`);
    return await res.json();
  },

  uploadDroneVideo: async (file: File): Promise<{ job_id: string; status: string; message: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/pipeline/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Video upload failed");
    }
    return await res.json();
  },

  fetchPipelineStatus: async (): Promise<{
    job_id: string | null;
    status: "idle" | "processing" | "completed" | "error";
    step: string;
    progress: number;
    details: any;
    error: string | null;
  }> => {
    const res = await fetch(`${API_BASE_URL}/api/pipeline/status`);
    if (!res.ok) throw new Error(`Status check failed: ${res.statusText}`);
    return await res.json();
  },

  getKaggleConfig: async (): Promise<{ configured: boolean; username: string }> => {
    const res = await fetch(`${API_BASE_URL}/api/pipeline/kaggle-config`);
    if (!res.ok) return { configured: false, username: "" };
    return await res.json();
  },

  uploadDroneVideoKaggle: async (file: File): Promise<{ job_id: string; status: string; message: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/pipeline/upload-kaggle`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Kaggle upload failed");
    }
    return await res.json();
  },

  importTrainedSplat: async (file: File): Promise<{ status: string; message: string; buildings_extracted: number }> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/pipeline/import-splat`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Splat import failed");
    }
    return await res.json();
  },

  resetPipeline: async (): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/api/pipeline/reset`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Reset failed");
    }
    return await res.json();
  },
};

export type Api = typeof api;
