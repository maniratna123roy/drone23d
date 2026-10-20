import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  ArrowLeft,
  Bot,
  Layers,
  Upload,
  Play,
  CheckCircle2,
  AlertCircle,
  FileDown,
  RefreshCw,
  Key,
  Video,
  Box,
  Eye,
  Building,
  ShieldAlert,
} from "lucide-react";
import { Viewer3DMesh } from "@/components/videogrammetry/Viewer3DMesh";

interface OpenRouterConfig {
  has_api_key: boolean;
  masked_key: string;
  default_model: string;
  supported_models: Array<{
    id: string;
    name: string;
    tier: string;
    speed: string;
  }>;
}

interface BuildingInfo {
  name: string;
  center: [number, number, number];
  dimensions: [number, number, number];
  rotation_deg: number;
  roof_type: string;
  facade_color_rgb: [number, number, number];
  roof_color_rgb: [number, number, number];
}

interface AnalysisReport {
  capture_id: string;
  created_at: string;
  model_used: string;
  prompt_used?: string;
  scene_data: {
    scene_title: string;
    confidence_score: number;
    architectural_summary: string;
    terrain?: { size_x: number; size_y: number; color_rgb: number[] };
    roads?: Array<{ start: number[]; end: number[]; width: number }>;
    buildings?: BuildingInfo[];
    vegetation?: Array<{ center: number[]; radius: number; height: number }>;
  };
  mesh_stats: {
    vertex_count: number;
    face_count: number;
    building_count: number;
    glb_size_bytes: number;
    obj_size_bytes: number;
  };
  artifacts: {
    glb_url: string;
    obj_url: string;
    report_url: string;
  };
}

const STAGES = [
  { id: 1, title: "1. Video Keyframe Sampling", desc: "Extracting sharp multi-angle aerial perspectives" },
  { id: 2, title: "2. OpenRouter Vision Analysis", desc: "Multimodal structural spatial perception & prompt alignment" },
  { id: 3, title: "3. 3D Architectural Synthesis", desc: "Generating volumetric meshes, facades, roofs & normals" },
  { id: 4, title: "4. Binary glTF 2.0 Compilation", desc: "Embedding vertex colors, surface normals & materials" },
];

const PROMPT_PRESETS = [
  {
    label: "🏭 Industrial Complex",
    text: "Reconstruct exact industrial warehouses with dual gable roofs, central communications tower (42m), asphalt access roads with white lane markings, and perimeter landscape verges.",
  },
  {
    label: "🏢 Commercial Campus",
    text: "Exact 3D replica of commercial glass office highrise with flat roof and mechanical penthouse, paved entrance roads, and multi-tier floor curtain walls.",
  },
  {
    label: "🏙️ Urban High-Rise",
    text: "Dense urban district with multi-story apartment towers, flat roofs with perimeter parapets, detailed window grid bands, and surrounding street network.",
  },
  {
    label: "🏟️ Sports Arena",
    text: "Curved roof sports pavilion and stadium structures with wide pedestrian sidewalks, parking lots, and surrounding landscaped tree clusters.",
  },
];

export const OpenRouter3DApp: React.FC = () => {
  const [config, setConfig] = useState<OpenRouterConfig | null>(null);
  const [apiKey, setApiKey] = useState<string>(() => {
    try {
      return localStorage.getItem("spatial_twin_openrouter_api_key") || "";
    } catch {
      return "";
    }
  });
  const [selectedModel, setSelectedModel] = useState<string>("nvidia/nemotron-3.5-super-vl:free");
  const [customKeyOpen, setCustomKeyOpen] = useState(false);

  const [selectedVideo, setSelectedVideo] = useState<File | null>(null);
  const [userPrompt, setUserPrompt] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStage, setActiveStage] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [glbUrl, setGlbUrl] = useState<string | undefined>(undefined);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch API configuration and prior models on mount
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/openrouter-3d/config")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setConfig(data);
          if (data.default_model) setSelectedModel(data.default_model);
        }
      })
      .catch((err) => console.warn("Backend not reached for OpenRouter config:", err));

    fetch("http://127.0.0.1:8000/api/openrouter-3d/models")
      .then((res) => (res.ok ? res.json() : []))
      .then((models) => {
        if (models && models.length > 0) {
          const latest = models[0];
          setReport(latest);
          if (latest.artifacts?.glb_url) {
            setGlbUrl(`http://127.0.0.1:8000${latest.artifacts.glb_url}?v=${Date.now()}`);
            setActiveStage(4);
          }
        }
      })
      .catch((err) => console.warn("No prior models loaded:", err));
  }, []);

  const handleStartGeneration = async (sampleMode: boolean = false) => {
    setIsProcessing(true);
    setErrorMsg(null);
    setActiveStage(1);

    const formData = new FormData();
    formData.append("sample_mode", sampleMode ? "true" : "false");
    if (apiKey) formData.append("api_key", apiKey);
    if (selectedModel) formData.append("model", selectedModel);
    if (userPrompt.trim()) formData.append("prompt", userPrompt.trim());
    if (!sampleMode && selectedVideo) {
      formData.append("video", selectedVideo);
    }

    // Advance simulated visual stage tracker while API executes
    const stageTimer1 = setTimeout(() => setActiveStage(2), 1200);
    const stageTimer2 = setTimeout(() => setActiveStage(3), 3500);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/openrouter-3d/generate", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `API responded with HTTP ${res.status}`);
      }

      const data: AnalysisReport = await res.json();
      setActiveStage(4);
      setReport(data);
      setGlbUrl(`http://127.0.0.1:8000${data.artifacts.glb_url}?v=${Date.now()}`);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to generate 3D model via OpenRouter");
    } finally {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-background text-foreground overflow-hidden font-sans">
      {/* Top Navigation & App Switcher */}
      <header className="border-b border-border/80 bg-background/95 backdrop-blur px-6 py-3 flex flex-wrap items-center justify-between gap-4 z-20">
        <div className="flex items-center gap-3">
          <a
            href="/demo"
            className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-cyan-400 transition-colors border border-border px-2.5 py-1.5 rounded"
            title="Switch to 3D Gaussian Splatting"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Gaussian Splatting</span>
          </a>

          <a
            href="/videogrammetry"
            className="flex items-center gap-1.5 text-xs font-mono text-purple-300 hover:text-white transition-colors border border-purple-500/50 bg-purple-500/10 px-2.5 py-1.5 rounded"
            title="Switch to Videogrammetry"
          >
            <Box className="h-3.5 w-3.5" />
            <span>Videogrammetry</span>
          </a>

          <div className="h-5 w-px bg-border/60" />

          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-emerald-500/20 border border-emerald-500/50 text-emerald-300">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-sm tracking-tight text-foreground uppercase">
                  OPENROUTER AI 3D
                </h1>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded border border-emerald-500/40 bg-emerald-950/60 text-emerald-300">
                  Multimodal Video-to-3D
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Vision LLM Scene Perception · Parametric 3D Geometry · Binary glTF 2.0
              </p>
            </div>
          </div>
        </div>

        {/* Status Badges & Controls */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 border border-border px-3 py-1.5 rounded bg-muted/40 font-mono text-[11px]">
            <Bot className="h-3.5 w-3.5 text-emerald-400" />
            <span className="text-muted-foreground">Model:</span>
            <span className="font-semibold text-emerald-300">{selectedModel.split("/").pop()}</span>
          </div>

          <div className="flex items-center gap-1.5 border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 rounded font-mono text-[11px] text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            <span>OpenRouter API Ready</span>
          </div>

          <button
            onClick={() => setCustomKeyOpen(!customKeyOpen)}
            className="flex items-center gap-1.5 border border-border px-2.5 py-1.5 rounded text-[11px] font-mono hover:border-emerald-500/60 transition-colors"
          >
            <Key className="h-3 w-3 text-muted-foreground" />
            <span>Key / Settings</span>
          </button>
        </div>
      </header>

      {/* Expandable API Key & Model Drawer */}
      {customKeyOpen && (
        <div className="border-b border-border bg-card/60 backdrop-blur px-6 py-3 flex flex-wrap items-center gap-4 text-xs font-mono animate-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-2 flex-1 min-w-[280px]">
            <span className="text-muted-foreground whitespace-nowrap">API Key:</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => {
                const val = e.target.value;
                setApiKey(val);
                try {
                  localStorage.setItem("spatial_twin_openrouter_api_key", val.trim());
                } catch {}
              }}
              placeholder="sk-or-v1-..."
              className="w-full bg-background border border-border rounded px-2.5 py-1 text-xs text-foreground focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-muted-foreground whitespace-nowrap">Model:</span>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-background border border-border rounded px-2.5 py-1 text-xs text-foreground focus:outline-none focus:border-emerald-500"
            >
              {config?.supported_models ? (
                config.supported_models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.speed})
                  </option>
                ))
              ) : (
                <>
                  <option value="nvidia/nemotron-3.5-super-vl:free">NVIDIA Nemotron 3.5 Super VL (Free)</option>
                  <option value="google/gemini-3.8-flash">Google Gemini 3.8 Flash</option>
                  <option value="google/gemini-3.7-flash">Google Gemini 3.7 Flash</option>
                  <option value="openai/gpt-4o">OpenAI GPT-4o</option>
                </>
              )}
            </select>
          </div>
        </div>
      )}

      {/* Main Grid View */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Left Control Column (Width 4/12) */}
        <div className="lg:col-span-4 border-r border-border/80 flex flex-col h-full overflow-y-auto p-5 gap-5 bg-card/20">
          {/* Section: Upload Video */}
          <div className="border border-border/80 rounded-lg p-4 bg-card/40 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Video className="h-3.5 w-3.5 text-emerald-400" />
                <span>1. Upload Drone Footage</span>
              </h2>
              {selectedVideo && (
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                  {(selectedVideo.size / (1024 * 1024)).toFixed(1)} MB
                </span>
              )}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setSelectedVideo(e.target.files[0]);
                }
              }}
            />

            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-border hover:border-emerald-500/60 transition-colors rounded-md p-5 flex flex-col items-center justify-center gap-2 cursor-pointer bg-background/50 text-center"
            >
              <Upload className="h-6 w-6 text-emerald-400/80" />
              <div>
                <p className="text-xs font-medium text-foreground">
                  {selectedVideo ? selectedVideo.name : "Drop drone video here, or browse"}
                </p>
                <p className="text-[10px] text-muted-foreground">Supports MP4, MOV, AVI (aerial footage)</p>
              </div>
            </div>

            {/* Section: Architectural Prompt Directive */}
            <div className="flex flex-col gap-2 pt-2 border-t border-border/60">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3 text-emerald-400" />
                  <span>2. Architectural Directive (Prompt)</span>
                </label>
                {userPrompt && (
                  <button
                    onClick={() => setUserPrompt("")}
                    className="text-[10px] text-muted-foreground hover:text-foreground font-mono"
                  >
                    Clear
                  </button>
                )}
              </div>

              <textarea
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                placeholder="Optional: Guide the AI with custom specifications (e.g. 'Reconstruct dual industrial warehouses with dual pitched roofs, central 42m tower, and asphalt roads with markings')..."
                rows={3}
                className="w-full bg-background/80 border border-border rounded p-2 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-emerald-500 font-mono resize-none"
              />

              {/* Quick Presets */}
              <div className="flex flex-wrap gap-1.5">
                {PROMPT_PRESETS.map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setUserPrompt(preset.text)}
                    className="text-[10px] border border-border/80 hover:border-emerald-500/50 bg-background/50 hover:bg-emerald-950/20 text-muted-foreground hover:text-emerald-300 px-2 py-0.5 rounded transition-colors"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button
                disabled={isProcessing}
                onClick={() => handleStartGeneration(false)}
                className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-black font-semibold text-xs py-2 px-3 rounded transition-all shadow-sm shadow-emerald-900/30"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>{isProcessing ? "Reconstructing 3D Scene..." : "Generate 3D Model"}</span>
              </button>

              <button
                disabled={isProcessing}
                onClick={() => handleStartGeneration(true)}
                className="flex items-center justify-center gap-1.5 border border-border hover:border-emerald-500/40 text-muted-foreground hover:text-foreground text-xs py-2 px-3 rounded transition-colors font-mono"
                title="Runs with diagnostic sample drone frames"
              >
                <span>Sample</span>
              </button>
            </div>

            {errorMsg && (
              <div className="flex items-start gap-2 p-2.5 rounded bg-red-950/40 border border-red-500/30 text-red-300 text-xs">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>

          {/* Section: Stage Pipeline Tracker */}
          <div className="border border-border/80 rounded-lg p-4 bg-card/40 flex flex-col gap-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-emerald-400" />
              <span>Pipeline Stages</span>
            </h2>

            <div className="flex flex-col gap-2">
              {STAGES.map((s) => {
                const isDone = activeStage > s.id;
                const isCurrent = activeStage === s.id;
                return (
                  <div
                    key={s.id}
                    className={`flex items-center justify-between p-2 rounded text-xs border transition-colors ${
                      isCurrent
                        ? "border-emerald-500/80 bg-emerald-950/30 text-emerald-200"
                        : isDone
                        ? "border-border/40 bg-muted/20 text-muted-foreground"
                        : "border-transparent text-muted-foreground/60"
                    }`}
                  >
                    <div>
                      <p className="font-medium">{s.title}</p>
                      <p className="text-[10px] text-muted-foreground">{s.desc}</p>
                    </div>
                    {isDone && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
                    {isCurrent && <RefreshCw className="h-3.5 w-3.5 text-emerald-400 animate-spin" />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section: AI Scene Analysis Report */}
          {report && (
            <div className="border border-border/80 rounded-lg p-4 bg-card/40 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Building className="h-3.5 w-3.5 text-emerald-400" />
                  <span>AI Structural Inventory</span>
                </h2>
                <span className="text-[10px] font-mono text-emerald-300 border border-emerald-500/30 bg-emerald-950/40 px-2 py-0.5 rounded">
                  Confidence: {report.scene_data.confidence_score}%
                </span>
              </div>

              <div>
                <p className="text-xs font-semibold text-foreground">{report.scene_data.scene_title}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">{report.scene_data.architectural_summary}</p>
              </div>

              {report.prompt_used && (
                <div className="p-2 rounded bg-emerald-950/20 border border-emerald-500/30 text-[10px] font-mono text-emerald-300">
                  <span className="text-muted-foreground">Directive: </span>
                  <span>{report.prompt_used}</span>
                </div>
              )}

              {/* Building List */}
              <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
                {report.scene_data.buildings?.map((b, i) => (
                  <div
                    key={i}
                    className="flex flex-col p-2 rounded bg-background/60 border border-border/60 text-xs font-mono"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-emerald-300">{b.name}</span>
                      <span className="text-[10px] text-muted-foreground capitalize">Roof: {b.roof_type}</span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1 flex gap-2">
                      <span>W: {b.dimensions[0]}m</span>
                      <span>D: {b.dimensions[1]}m</span>
                      <span className="text-emerald-400">H: {b.dimensions[2]}m</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Download Artifacts */}
              <div className="flex items-center gap-2 pt-2 border-t border-border/60">
                <a
                  href={`http://127.0.0.1:8000${report.artifacts.glb_url}`}
                  download="scene.glb"
                  className="flex-1 flex items-center justify-center gap-1.5 border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 text-xs py-1.5 rounded transition-colors font-mono"
                >
                  <FileDown className="h-3.5 w-3.5" />
                  <span>Download .GLB</span>
                </a>

                <a
                  href={`http://127.0.0.1:8000${report.artifacts.obj_url}`}
                  download="mesh.obj"
                  className="flex items-center justify-center gap-1.5 border border-border hover:border-foreground/40 text-muted-foreground text-xs py-1.5 px-3 rounded transition-colors font-mono"
                >
                  <FileDown className="h-3.5 w-3.5" />
                  <span>.OBJ</span>
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Right 3D Interactive Viewport (Width 8/12) */}
        <div className="lg:col-span-8 flex flex-col h-full bg-black relative">
          {/* Floating Glass Viewport HUD */}
          {report && (
            <div className="absolute top-4 left-4 z-10 flex flex-wrap items-center gap-2 pointer-events-auto bg-background/80 backdrop-blur border border-border/70 rounded-md px-3 py-1.5 text-[11px] font-mono shadow-md">
              <span className="font-semibold text-foreground">{report.scene_data.scene_title}</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-emerald-400">
                {report.mesh_stats.building_count} {report.mesh_stats.building_count === 1 ? "Building" : "Buildings"}
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="text-cyan-400">
                {report.mesh_stats.face_count.toLocaleString()} Polygons
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="text-purple-400">Surface Normals Active</span>
            </div>
          )}

          <Viewer3DMesh
            modelReady={Boolean(glbUrl)}
            tierId="openrouter_ai_3d"
            modelUrl={glbUrl}
            captureId={report?.capture_id || "ai3d_viewer"}
          />
        </div>
      </div>
    </div>
  );
};
