/**
 * Mock data layer. All values here are synthetic and exist purely so the UI
 * can be developed ahead of the real backend. No component should define its
 * own data — everything flows through `api.ts`.
 */
import type {
  Layer,
  Mission,
  ProcessingJob,
  Project,
  Scene,
  SpatialEdit,
  SpatialObject,
  SpatialQuery,
} from "@/types/spatial";

/** deterministic pseudo-random so the scene is identical on server + client */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const LAYER_LABELS: Record<Layer["id"], string> = {
  buildings: "Buildings",
  roads: "Roads",
  terrain: "Terrain",
  vegetation: "Vegetation",
  infrastructure: "Infrastructure",
};

function buildObjects(): SpatialObject[] {
  const rand = rng(20260927);
  const objects: SpatialObject[] = [];

  // Buildings laid out on an irregular block grid
  let index = 1;
  for (let gx = -3; gx <= 3; gx++) {
    for (let gz = -2; gz <= 2; gz++) {
      if (gx === 0 && Math.abs(gz) > 1) continue; // avenue
      if (rand() < 0.18) continue;
      const jitterX = (rand() - 0.5) * 0.5;
      const jitterZ = (rand() - 0.5) * 0.5;
      const core = Math.max(0, 1 - (Math.abs(gx) + Math.abs(gz)) / 5);
      const height = 8 + core * 26 + rand() * 14;
      const width = 1.1 + rand() * 0.7;
      const depth = 1.1 + rand() * 0.7;
      objects.push({
        id: `bld-${String(index).padStart(2, "0")}`,
        label: `Building ${String(index).padStart(2, "0")}`,
        layer: "buildings",
        x: gx * 2.6 + jitterX,
        z: gz * 2.6 + jitterZ,
        width,
        depth,
        height: Number(height.toFixed(1)),
        elevationM: Number((112 + rand() * 24).toFixed(1)),
        areaM2: Math.round(width * depth * 620),
      });
      index++;
    }
  }

  // Vegetation clusters
  for (let i = 0; i < 14; i++) {
    const x = (rand() - 0.5) * 20;
    const z = (rand() - 0.5) * 16;
    objects.push({
      id: `veg-${i}`,
      label: `Canopy ${i + 1}`,
      layer: "vegetation",
      x,
      z,
      width: 0.6 + rand() * 0.6,
      depth: 0.6 + rand() * 0.6,
      height: Number((3 + rand() * 5).toFixed(1)),
      elevationM: Number((110 + rand() * 20).toFixed(1)),
      areaM2: Math.round(140 + rand() * 260),
    });
  }

  // Infrastructure masts / tanks
  for (let i = 0; i < 6; i++) {
    const x = (rand() - 0.5) * 18;
    const z = (rand() - 0.5) * 14;
    objects.push({
      id: `inf-${i}`,
      label: `Mast ${i + 1}`,
      layer: "infrastructure",
      x,
      z,
      width: 0.22,
      depth: 0.22,
      height: Number((22 + rand() * 18).toFixed(1)),
      elevationM: Number((118 + rand() * 12).toFixed(1)),
      areaM2: Math.round(30 + rand() * 40),
    });
  }

  return objects;
}

const OBJECTS = buildObjects();

function layers(): Layer[] {
  return (Object.keys(LAYER_LABELS) as Layer["id"][]).map((id) => ({
    id,
    label: LAYER_LABELS[id],
    count:
      id === "roads"
        ? 9
        : id === "terrain"
          ? 1
          : OBJECTS.filter((o) => o.layer === id).length,
    enabled: true,
  }));
}

const PROJECT: Project = {
  id: "prj-aurora",
  name: "Aurora Basin",
  location: "Sector 14 / North Ridge",
  coordinates: { lat: 47.6205, lng: -122.3493 },
  createdAt: "2026-04-12T09:20:00Z",
  missionIds: ["msn-001"],
};

const MISSIONS: Mission[] = [
  {
    id: "msn-001",
    projectId: PROJECT.id,
    label: "Single pass · north-east transect",
    durationSec: 412,
    altitudeM: 118,
    frames: 12360,
    capturedAt: "2026-04-12T10:04:00Z",
  },
];

const PIPELINE: ProcessingJob[] = [
  {
    id: "job-capture",
    missionId: "msn-001",
    stage: "capture",
    progress: 1,
    status: "complete",
    metrics: [
      { label: "Frames", value: "12,360" },
      { label: "Telemetry", value: "GNSS + IMU" },
      { label: "Altitude", value: "118 M" },
    ],
  },
  {
    id: "job-reconstruction",
    missionId: "msn-001",
    stage: "reconstruction",
    progress: 1,
    status: "complete",
    metrics: [
      { label: "Camera poses", value: "1,204" },
      { label: "Points", value: "8.4 M" },
      { label: "Mean error", value: "0.42 PX" },
    ],
  },
  {
    id: "job-semantics",
    missionId: "msn-001",
    stage: "semantics",
    progress: 1,
    status: "complete",
    metrics: [
      { label: "Classes", value: "5" },
      { label: "Objects", value: String(OBJECTS.length) },
      { label: "Confidence", value: "0.93" },
    ],
  },
  {
    id: "job-intelligence",
    missionId: "msn-001",
    stage: "intelligence",
    progress: 1,
    status: "complete",
    metrics: [
      { label: "Index", value: "PostGIS" },
      { label: "Queries", value: "Natural language" },
      { label: "Latency", value: "180 MS" },
    ],
  },
];

const SCENE: Scene = {
  id: "scn-aurora-01",
  projectId: PROJECT.id,
  boundsM: [1840, 1420],
  pointCount: 8_400_000,
  objects: OBJECTS,
  layers: layers(),
};

const TALL_BUILDINGS = OBJECTS.filter(
  (o) => o.layer === "buildings" && o.height > 20,
)
  .slice(0, 7)
  .map((o) => o.id);

const CENTRAL_BUILDINGS = OBJECTS.filter(
  (o) => o.layer === "buildings" && Math.abs(o.x) < 3.2 && Math.abs(o.z) < 3.2,
)
  .slice(0, 7)
  .map((o) => o.id);

const QUERIES: SpatialQuery[] = [
  {
    id: "qry-01",
    prompt: "Which buildings exceed 20 meters?",
    resultLabel: "Buildings found",
    resultValue: "07",
    matchedObjectIds: TALL_BUILDINGS,
  },
  {
    id: "qry-02",
    prompt: "How far is Building 12 from the nearest road?",
    resultLabel: "Distance",
    resultValue: "42.8 M",
    matchedObjectIds: ["bld-12"],
  },
];

const EDITS: SpatialEdit[] = [
  {
    id: "edt-01",
    command: "Make the central buildings 40m taller.",
    targetObjectIds: CENTRAL_BUILDINGS,
    operation: "extrude",
    deltaM: 40,
    status: { objects: 7, delta: "+40 M", state: "Preview ready" },
  },
  {
    id: "edt-02",
    command: "Raise the valley floor by 20 meters.",
    targetObjectIds: [],
    operation: "raise-terrain",
    deltaM: 20,
    status: { objects: 1, delta: "+20 M", state: "Preview ready" },
  },
];

const latency = <T>(value: T): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(value), 120));

export const getProject = () => latency(PROJECT);
export const getMissions = () => latency(MISSIONS);
export const getPipeline = () => latency(PIPELINE);
export const getScene = () => latency(SCENE);
export const getQueries = () => latency(QUERIES);
export const getEdits = () => latency(EDITS);

/** Synchronous accessors for the 3D scenes (no loading state in-canvas). */
export const sceneSync = SCENE;
export const queriesSync = QUERIES;
export const editsSync = EDITS;
export const pipelineSync = PIPELINE;
