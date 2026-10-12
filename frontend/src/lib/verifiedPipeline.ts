import type {
  PipelineStatus,
  VerifiedSceneManifest,
  VerifiedSceneResponse,
} from "../types/spatial.ts";
import { parseGaussianSplat } from "../components/three/gaussian-data.ts";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
function vector(value: unknown): value is [number, number, number] {
  return Array.isArray(value) && value.length === 3 && value.every(finite);
}
function text(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

/** Fail closed: old mutable assets and unrelated/metric scenes are never accepted. */
export function parseVerifiedScene(value: unknown): VerifiedSceneResponse {
  if (!record(value)) throw new Error("Invalid verified-scene response.");
  if (value["status"] === "empty" && value["manifest"] === null)
    return { status: "empty", manifest: null };
  const m = value["manifest"];
  if (
    value["status"] !== "ready" ||
    !record(m) ||
    m["schema_version"] !== 1 ||
    !text(m["job_id"]) ||
    !/^[a-zA-Z0-9_-]+$/.test(m["job_id"]) ||
    !text(m["version"]) ||
    !text(m["source_name"]) ||
    !text(m["created_at"]) ||
    !Number.isFinite(Date.parse(m["created_at"])) ||
    !Number.isSafeInteger(m["gaussian_count"]) ||
    (m["gaussian_count"] as number) <= 0 ||
    !["COLMAP_PHASE_A", "ALIGNED_GROUND", "SCENE_METRIC"].includes(
      m["coordinate_frame"] as string,
    ) ||
    !["RELATIVE_UNCALIBRATED", "METRIC_APPROXIMATE", "CALIBRATED"].includes(
      m["scale_status"] as string,
    ) ||
    !["UNKNOWN", "EXTRACTED_STRUCTURES", "KNOWN", "CLASSIFIED_MULTIVIEW"].includes(
      m["semantics"] as string,
    ) ||
    !record(m["capabilities"]) ||
    typeof m["capabilities"]["queries"] !== "boolean" ||
    typeof m["capabilities"]["edits"] !== "boolean" ||
    (m["semantics"] === "UNKNOWN" &&
      (m["capabilities"]["queries"] !== false || m["capabilities"]["edits"] !== false)) ||
    m["splat_url"] !== `/static/scenes/${m["job_id"]}/scene.splat` ||
    m["classes_url"] !== `/static/scenes/${m["job_id"]}/scene.classes.u8` ||
    !record(m["quality"])
  ) {
    throw new Error(
      "The server did not provide a supported verified, versioned COLMAP scene manifest.",
    );
  }
  if (m["semantics"] === "CLASSIFIED_MULTIVIEW") {
    const classification = m["classification"];
    const capabilities = m["capabilities"] as Record<string, unknown>;
    if (
      !record(classification) ||
      classification["method"] !== "SEGFORMER_DEPTH_VISIBLE_MULTIVIEW" ||
      !record(classification["class_counts"]) ||
      !["structure", "terrain", "road", "vegetation", "unknown"].every((name) => {
        const count = (classification["class_counts"] as Record<string, unknown>)[name];
        return Number.isSafeInteger(count) && (count as number) >= 0;
      }) ||
      Object.values(classification["class_counts"]).reduce<number>(
        (sum, n) => sum + Number(n),
        0,
      ) !== m["gaussian_count"] ||
      !finite(classification["classified_fraction"]) ||
      classification["classified_fraction"] <= 0 ||
      classification["classified_fraction"] > 1 ||
      !Number.isSafeInteger(classification["views"]) ||
      (classification["views"] as number) < 2 ||
      capabilities["queries"] ||
      capabilities["edits"]
    ) {
      throw new Error(
        "Invalid multi-view classification evidence or unsupported metric capabilities.",
      );
    }
  }
  const bounds = m["bounds"],
    camera = m["camera"];
  if (
    !record(bounds) ||
    !vector(bounds["min"]) ||
    !vector(bounds["max"]) ||
    bounds["min"].some((v, i) => v > (bounds["max"] as number[])[i]!) ||
    !record(camera) ||
    !vector(camera["position"]) ||
    !vector(camera["target"]) ||
    !vector(camera["up"]) ||
    !finite(camera["fov_y_degrees"]) ||
    camera["fov_y_degrees"] <= 0 ||
    camera["fov_y_degrees"] >= 180 ||
    !finite(camera["near"]) ||
    !finite(camera["far"]) ||
    camera["near"] <= 0 ||
    camera["far"] <= camera["near"]
  ) {
    throw new Error("The verified scene has invalid bounds or source camera parameters.");
  }
  const direction = camera["target"].map((v, i) => v - (camera["position"] as number[])[i]!);
  const up = camera["up"];
  const cross = [
    direction[1]! * up[2] - direction[2]! * up[1],
    direction[2]! * up[0] - direction[0]! * up[2],
    direction[0]! * up[1] - direction[1]! * up[0],
  ];
  if (Math.hypot(...direction) === 0 || Math.hypot(...up) === 0 || Math.hypot(...cross) === 0) {
    throw new Error("The source camera must have a direction and a nonparallel up vector.");
  }
  return { status: "ready", manifest: m as unknown as VerifiedSceneManifest };
}

export function parsePipelineStatus(value: unknown): PipelineStatus {
  if (
    !record(value) ||
    !["idle", "processing", "completed", "error"].includes(String(value["status"])) ||
    !(value["job_id"] === null || text(value["job_id"])) ||
    (value["status"] !== "idle" && !text(value["job_id"])) ||
    typeof value["step"] !== "string" ||
    !finite(value["progress"]) ||
    value["progress"] < 0 ||
    value["progress"] > 100 ||
    !record(value["details"]) ||
    !(value["error"] === null || typeof value["error"] === "string")
  ) {
    throw new Error("Invalid pipeline status response; the last known state is retained.");
  }
  return value as unknown as PipelineStatus;
}

export function validateVideo(file: Pick<File, "name" | "size">): void {
  if (!/\.(mp4|mov|avi|mkv)$/i.test(file.name))
    throw new Error("Choose a local MP4, MOV, AVI, or MKV video.");
  if (file.size <= 0) throw new Error("The selected video is empty.");
}

async function requireOk(response: Response, label: string): Promise<Response> {
  if (response.ok) return response;
  const body: unknown = await response.json().catch(() => null);
  const detail = record(body) && text(body["detail"]) ? body["detail"] : `HTTP ${response.status}`;
  throw new Error(`${label}: ${detail}`);
}

/** Injectable transport keeps the real wire contract testable without browser mocks. */
export function createVerifiedPipelineApi(baseUrl: string, transport: typeof fetch = fetch) {
  const base = baseUrl.replace(/\/$/, "");
  return {
    async scene(signal: AbortSignal): Promise<VerifiedSceneResponse> {
      const response = await requireOk(
        await transport(`${base}/api/pipeline/scene`, { signal, cache: "no-store" }),
        "Scene check failed",
      );
      return parseVerifiedScene(await response.json());
    },
    async status(signal: AbortSignal, jobId?: string): Promise<PipelineStatus> {
      const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
      const response = await requireOk(
        await transport(`${base}/api/pipeline/status${query}`, { signal, cache: "no-store" }),
        "Status check failed",
      );
      return parsePipelineStatus(await response.json());
    },
    async upload(
      file: File,
      signal: AbortSignal,
    ): Promise<{ job_id: string; status: "processing"; message: string }> {
      validateVideo(file);
      const body = new FormData();
      body.append("file", file);
      const response = await requireOk(
        await transport(`${base}/api/pipeline/upload`, { method: "POST", body, signal }),
        "Upload failed",
      );
      const result: unknown = await response.json();
      if (
        !record(result) ||
        !text(result["job_id"]) ||
        result["status"] !== "processing" ||
        typeof result["message"] !== "string"
      ) {
        throw new Error(
          "The upload response did not identify an accepted pipeline job. Refresh status before retrying.",
        );
      }
      return result as { job_id: string; status: "processing"; message: string };
    },
    async assets(manifest: VerifiedSceneManifest, signal: AbortSignal) {
      // Revalidate even if called outside the polling path. Never follow arbitrary asset URLs.
      parseVerifiedScene({ status: "ready", manifest });
      const [splat, classes] = await Promise.all([
        transport(`${base}${manifest.splat_url}`, { signal }).then((r) =>
          requireOk(r, "Gaussian file failed"),
        ),
        transport(`${base}${manifest.classes_url}`, { signal }).then((r) =>
          requireOk(r, "Class sidecar failed"),
        ),
      ]);
      const [binary, sidecar] = await Promise.all([splat.arrayBuffer(), classes.arrayBuffer()]);
      if (signal.aborted) throw new DOMException("Scene loading cancelled", "AbortError");
      return parseGaussianSplat(
        binary,
        sidecar,
        manifest.gaussian_count,
        manifest.semantics === "CLASSIFIED_MULTIVIEW",
      );
    },
  };
}

export type VerifiedPipelineApi = ReturnType<typeof createVerifiedPipelineApi>;
