import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  Box,
  Building2,
  Edit3,
  Layers,
  Info,
  Palette,
  RefreshCw,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";
import { useVerifiedPipeline } from "@/hooks/useVerifiedPipeline";
import { manifestKey } from "@/lib/verifiedPipelineSession";
import { API_BASE_URL, api } from "@/lib/api";
import { useSpatialStore } from "@/store/spatialStore";
import { SceneCanvas } from "./three/SceneCanvas";
import { SplatRenderer } from "./three/SplatRenderer";
import { CameraControls } from "./three/CameraControls";
import { HoveredObjectDetails, ProxyMeshes } from "./three/ProxyMeshes";
import { GhostOverlay } from "./three/GhostOverlay";
import { QueryBox } from "./QueryBox";
import { EditBox } from "./EditBox";
import { ObjectInspector } from "./ObjectInspector";
import { SemanticAttributesInventory } from "./SemanticAttributesInventory";
import { LayerControls } from "./LayerControls";
import { SEMANTIC_CLASSES, semanticCounts } from "./three/semantic-display";

class ViewerErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  override state: { error: string | null } = { error: null };
  static getDerivedStateFromError(error: unknown) {
    return {
      error: error instanceof Error ? error.message : "The browser could not render this scene.",
    };
  }
  override render() {
    if (this.state.error)
      return (
        <div role="alert" className="p-6 text-red-300">
          Viewer error: {this.state.error}. The verified files are unchanged; reload to retry.
        </div>
      );
    return this.props.children;
  }
}

/** The landing-page showcase is deliberately separate from this verified, local-only workspace. */
export function SpatialTwinApp() {
  const pipeline = useVerifiedPipeline();
  const fileInput = useRef<HTMLInputElement>(null);
  const [resetCamera, setResetCamera] = useState(0);
  const [activeTab, setActiveTab] = useState<
    "query" | "edit" | "inspector" | "classes" | "layers" | "info"
  >("query");
  const [aligning, setAligning] = useState(false);
  const [alignError, setAlignError] = useState<string | null>(null);
  const [hiddenClasses, setHiddenClasses] = useState<number[]>([]);
  const [semanticColors, setSemanticColors] = useState(true);

  const { status, manifest, displayed } = pipeline;
  const { selectedObjectId, objects, queryFilterActive, highlightedObjectIds } = useSpatialStore();
  const visibleObjectBboxes = useMemo(
    () => objects.filter((object) => highlightedObjectIds.includes(object.id) && object.splatBbox).map((object) => object.splatBbox!),
    [objects, highlightedObjectIds],
  );

  const busy = pipeline.uploading || status?.status === "processing";
  const previous =
    displayed !== null &&
    ((status?.job_id != null &&
      status.job_id !== displayed.manifest.job_id &&
      status.job_id !== displayed.manifest.source_job_id) ||
      (manifest !== null && manifestKey(manifest) !== manifestKey(displayed.manifest)));
  const key = displayed ? manifestKey(displayed.manifest) : "empty";

  const hasIntelligence = Boolean(displayed?.manifest.capabilities?.queries);
  const classified =
    displayed?.manifest.semantics === "CLASSIFIED_MULTIVIEW" ||
    displayed?.manifest.semantics === "EXTRACTED_STRUCTURES";
  const counts = useMemo(
    () => (displayed ? semanticCounts(displayed.data.classes) : {}),
    [displayed],
  );

  // Sync structures from PostGIS when capable scene loads
  useEffect(() => {
    if (hasIntelligence) {
      api
        .fetchBackendStructures()
        .then((objs) => {
          useSpatialStore.getState().setObjects(objs);
        })
        .catch((err) => {
          console.warn("[SpatialTwinApp] Failed to load PostGIS structures:", err);
        });
    }
  }, [hasIntelligence, displayed?.manifest.version]);

  // Switch to inspector tab if user clicks a proxy mesh
  useEffect(() => {
    if (selectedObjectId && hasIntelligence) {
      setActiveTab("inspector");
    }
  }, [selectedObjectId, hasIntelligence]);

  const handleAlignStructures = async () => {
    setAligning(true);
    setAlignError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/pipeline/align-structures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Alignment failed" }));
        throw new Error(err.detail || "Alignment request failed");
      }
      await pipeline.refresh();
      const objs = await api.fetchBackendStructures();
      useSpatialStore.getState().setObjects(objs);
      setActiveTab("query");
    } catch (err) {
      setAlignError(err instanceof Error ? err.message : "Failed to align structures");
    } finally {
      setAligning(false);
    }
  };

  return (
    <main className="w-full h-screen bg-background flex flex-col overflow-hidden text-foreground">
      <header className="min-h-14 border-b border-border/60 px-4 py-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Box className="h-4 w-4 text-cyan-400" /> Spatial Twin
          <span className="text-xs font-normal text-muted-foreground">
            Drone-Captured Digital Twin
          </span>
          {hasIntelligence ? (
            <span className="ml-2 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/70 text-emerald-400 border border-emerald-500/30">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              PostGIS 3D Twin · AI Enabled
            </span>
          ) : (
            <span className="ml-2 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-950/70 text-amber-400 border border-amber-500/30">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              {classified ? "3DGS · Classified" : "3DGS · Classes pending"}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <button
            type="button"
            disabled={busy || pipeline.checking}
            onClick={() => fileInput.current?.click()}
            className="flex items-center gap-2 rounded border border-cyan-500/40 px-3 py-2 text-cyan-300 disabled:opacity-50 hover:bg-cyan-950/30 transition-colors"
          >
            <Upload className="h-4 w-4" /> {pipeline.uploading ? "Uploading…" : "Upload video"}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".mp4,.mov,.avi,.mkv"
            className="hidden"
            aria-label="Local drone video"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) pipeline.upload(file);
            }}
          />
          <button
            type="button"
            onClick={pipeline.refresh}
            className="flex items-center gap-1 rounded border border-border px-2.5 py-2 hover:bg-muted/50 transition-colors"
            title="Refresh durable job status and retry the latest verified files"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <a
            href="/"
            className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Showcase
          </a>
        </div>
      </header>

      <div className="flex-1 min-h-0 flex flex-col md:flex-row">
        {/* Left Interactive Sidebar */}
        <aside className="w-full md:w-96 md:shrink-0 max-h-[50vh] md:max-h-none overflow-y-auto border-b md:border-b-0 md:border-r border-border/60 p-4 space-y-4 text-sm flex flex-col">
          {/* Tab Navigation */}
          <nav className="flex items-center gap-1 border-b border-border/60 pb-2 overflow-x-auto shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab("query")}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors shrink-0 ${
                activeTab === "query"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              }`}
            >
              <Search className="h-3.5 w-3.5" /> Query
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("edit")}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors shrink-0 ${
                activeTab === "edit"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              }`}
            >
              <Edit3 className="h-3.5 w-3.5" /> Edit
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("inspector")}
              className={`relative flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors shrink-0 ${
                activeTab === "inspector"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              }`}
            >
              <Building2 className="h-3.5 w-3.5" /> Inspector
              {selectedObjectId && <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />}
            </button>
            {classified && (
              <button
                type="button"
                onClick={() => setActiveTab("classes")}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors shrink-0 ${
                  activeTab === "classes"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                }`}
                title="Surface Classification"
              >
                <Palette className="h-3.5 w-3.5" /> Classes
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveTab("layers")}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors shrink-0 ${
                activeTab === "layers"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              }`}
            >
              <Layers className="h-3.5 w-3.5" /> Layers
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("info")}
              className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium transition-colors shrink-0 ${
                activeTab === "info"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              }`}
              title="Scene Metadata"
            >
              <Info className="h-3.5 w-3.5" />
            </button>
          </nav>

          {/* Tab Contents */}
          <div className="flex-1 overflow-y-auto space-y-4">
            {/* If user is in Query, Edit, or Inspector but intelligence is not yet activated */}
            {!hasIntelligence && (activeTab === "query" || activeTab === "edit" || activeTab === "inspector") ? (
              <section className="rounded-lg border border-cyan-500/40 bg-cyan-950/20 p-3.5 space-y-3">
                <div className="flex items-center gap-2 text-cyan-300 font-semibold text-sm">
                  <Sparkles className="h-4 w-4" />
                  Semantic Alignment & Intelligence
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Surface classes identify what was observed. Metric queries and edits also require
                  calibrated scale, a ground frame, and matching PostGIS objects.
                </p>
                {alignError && (
                  <p role="alert" className="text-xs text-red-300">
                    {alignError}
                  </p>
                )}
                <button
                  type="button"
                  disabled={aligning || !displayed}
                  onClick={handleAlignStructures}
                  className="w-full flex items-center justify-center gap-2 rounded bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium p-2.5 shadow-lg shadow-cyan-900/20 disabled:opacity-50 text-xs transition-all cursor-pointer"
                >
                  {aligning ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  {aligning
                    ? "Extracting PostGIS 3D Structures…"
                    : "⚡ Align Ground & Extract PostGIS Buildings"}
                </button>
              </section>
            ) : null}

            {/* Active Tab Views */}
            {hasIntelligence && activeTab === "query" && <QueryBox />}
            {hasIntelligence && activeTab === "edit" && <EditBox />}
            {activeTab === "inspector" && <ObjectInspector />}

            {/* Surface Classification & Physical Attributes View */}
            {activeTab === "classes" && (
              <div className="space-y-4">
                {classified && (
                  <section
                    aria-label="Semantic classification"
                    className="space-y-3 rounded border border-border p-3"
                  >
                    <div className="flex items-center justify-between">
                      <h2 className="font-semibold text-sm">Surface classification</h2>
                      <span className="text-xs text-cyan-400 font-medium">SegFormer AI</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Multi-view AI predictions · counts are Gaussians, not individual objects.
                    </p>
                    <label className="flex gap-2 items-center text-xs font-medium cursor-pointer">
                      <input
                        type="checkbox"
                        checked={semanticColors}
                        onChange={(event) => setSemanticColors(event.target.checked)}
                      />
                      Show class colors in 3D viewer
                    </label>
                    <div className="space-y-2 pt-1 border-t border-border/40">
                      {SEMANTIC_CLASSES.map((item) => (
                        <label key={item.id} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-muted/30 p-1 rounded">
                          <input
                            type="checkbox"
                            checked={!hiddenClasses.includes(item.id)}
                            onChange={(event) =>
                              setHiddenClasses((old) =>
                                event.target.checked
                                  ? old.filter((id) => id !== item.id)
                                  : [...old, item.id],
                              )
                            }
                          />
                          <span
                            className="h-2.5 w-2.5 rounded shrink-0"
                            style={{ backgroundColor: `rgb(${item.color.join(",")})` }}
                          />
                          <span className="flex-1">{item.label}</span>
                          <span className="font-mono text-muted-foreground">{(counts[item.id] ?? 0).toLocaleString()}</span>
                        </label>
                      ))}
                    </div>
                  </section>
                )}

                {/* Live Measured Physical Inventory for Buildings, Roads, Vegetation, Terrain */}
                <SemanticAttributesInventory
                  initialAttributes={displayed?.manifest?.classification?.attributes}
                  onInspectObject={() => setActiveTab("inspector")}
                />
              </div>
            )}

            {/* Layer Controls View */}
            {activeTab === "layers" && <LayerControls />}

            {/* Scene Info & Diagnostics View */}
            {activeTab === "info" && (
              <div className="space-y-4">
                <section aria-label="Pipeline job" aria-live="polite" className="space-y-2">
                  <h1 className="font-semibold text-sm">Reconstruction job</h1>
                  <p className="text-xs">
                    {pipeline.uploading
                      ? "Uploading video to this machine…"
                      : pipeline.checking
                        ? "Checking saved job status…"
                        : status?.status === "idle"
                          ? "No reconstruction job yet."
                          : status
                            ? `${status.status.toUpperCase()}: ${status.step || "Waiting for the next stage"}`
                            : "Job status unavailable."}
                  </p>
                  {status?.job_id && (
                    <p className="font-mono text-xs break-all text-muted-foreground">Job: {status.job_id}</p>
                  )}
                  {status?.status === "processing" && (
                    <>
                      <progress
                        className="w-full accent-cyan-400"
                        max={100}
                        value={status.progress}
                        aria-label="Reconstruction progress"
                      />
                      <p className="text-xs text-muted-foreground">
                        {status.progress.toFixed(0)}% — this can take time. Reloading this page does
                        not stop the server job.
                      </p>
                    </>
                  )}
                  {status?.status === "error" && (
                    <p
                      role="alert"
                      className="rounded border border-red-500/50 p-3 text-red-300 text-xs"
                    >
                      Reconstruction failed: {status.error}
                    </p>
                  )}
                </section>

                {displayed && (
                  <section aria-label="Reconstruction job" className="space-y-2 pt-2 border-t border-border/40">
                    <h2 className="font-semibold text-sm">
                      {previous ? "Previous verified scene" : "Verified 3D Scene"}
                    </h2>
                    <p className="text-xs text-muted-foreground font-mono break-all">
                      Job: {displayed.manifest.job_id}
                    </p>
                    <p className="text-xs text-muted-foreground font-mono break-all">
                      Source: {displayed.manifest.source_name}
                    </p>
                    <p className="text-xs font-mono text-muted-foreground break-all">
                      Version: {displayed.manifest.version}
                    </p>
                    <p className="text-xs">
                      {displayed.data.count.toLocaleString()} learned Gaussians
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Frame: <span className="font-mono text-cyan-300">{displayed.manifest.coordinate_frame}</span> · Scale: <span className="font-mono text-cyan-300">{displayed.manifest.scale_status}</span>
                    </p>
                    <button
                      type="button"
                      className="mt-2 w-full rounded border border-border px-3 py-1.5 text-xs hover:bg-muted/40 cursor-pointer"
                      onClick={() => setResetCamera((v) => v + 1)}
                    >
                      Reset to source camera
                    </button>
                  </section>
                )}

                {status && Object.keys(status.details).length > 0 && (
                  <details className="pt-2 border-t border-border/40">
                    <summary className="cursor-pointer text-xs text-muted-foreground">
                      Job diagnostics
                    </summary>
                    <pre className="mt-2 whitespace-pre-wrap break-all text-xs bg-muted/30 p-2 rounded">
                      {JSON.stringify(status.details, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* 3D Viewport */}
        <section
          className="flex-1 min-h-[300px] relative bg-black"
          aria-label="Verified Gaussian viewer"
        >
          {displayed ? (
            <ViewerErrorBoundary key={key}>
              <SceneCanvas
                className="w-full h-full"
                sourceFrame={displayed.manifest.coordinate_frame === "COLMAP_PHASE_A" ? "COLMAP_PHASE_A" : undefined}
                camera={{
                  position: displayed.manifest.camera.position,
                  up: displayed.manifest.camera.up,
                  fov: displayed.manifest.camera.fov_y_degrees,
                  near: displayed.manifest.camera.near,
                  far: displayed.manifest.camera.far,
                }}
              >
                <SplatRenderer
                  data={displayed.data}
                  hiddenClasses={hiddenClasses}
                  semanticColors={semanticColors}
                  queryFilterActive={queryFilterActive}
                  visibleObjectBboxes={visibleObjectBboxes}
                />
                {hasIntelligence && (
                  <>
                    <ProxyMeshes />
                    <HoveredObjectDetails />
                    <GhostOverlay />
                  </>
                )}
                <CameraControls sourceCamera={displayed.manifest.camera} resetToken={resetCamera} />
              </SceneCanvas>
            </ViewerErrorBoundary>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center gap-3">
              <Box className="h-9 w-9 text-muted-foreground" />
              <h2 className="text-lg font-semibold">
                {pipeline.checking
                  ? "Checking for a verified scene…"
                  : pipeline.loadingAssets
                    ? "Checking published Gaussian files…"
                    : "No verified reconstruction yet"}
              </h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Upload a local video. A scene appears only after camera, dense geometry, and
                photometric verification succeed. No sample scene or placeholder buildings are
                substituted.
              </p>
            </div>
          )}

          {displayed && (
            <div className="absolute bottom-3 left-3 right-3 pointer-events-none rounded bg-black/80 backdrop-blur border border-white/10 p-2 text-center text-xs text-gray-300 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {previous && <strong className="text-amber-300">Previous verified scene · </strong>}
                <span>Left drag: orbit · Right drag / Shift+drag: pan · Wheel: zoom</span>
                {hasIntelligence && <span> · Click building: inspect</span>}
                {classified && (
                  <button
                    type="button"
                    onClick={() => setSemanticColors((v) => !v)}
                    className="pointer-events-auto ml-2 px-2 py-0.5 rounded border border-cyan-500/40 bg-cyan-950/40 hover:bg-cyan-900/50 text-cyan-300 text-[11px] font-medium transition-colors cursor-pointer"
                    title="Toggle semantic classification colors vs photoreal RGB"
                  >
                    🎨 Colors: {semanticColors ? "Classified" : "Photoreal"}
                  </button>
                )}
              </div>
              <div className="text-[11px] text-muted-foreground font-mono">
                {hasIntelligence
                  ? "Coordinate Frame: PostGIS Metric"
                  : "Coordinate Frame: Relative"}
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
