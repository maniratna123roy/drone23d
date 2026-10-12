import { motion, useTransform } from "motion/react";
import {
  Upload,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RotateCcw,
  Play,
  Zap,
  Cloud,
  ExternalLink,
  FileCode,
} from "lucide-react";
import { useRef, useState, useEffect, type ChangeEvent, type DragEvent } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { SceneCanvas } from "@/components/three/SceneCanvas";
import {
  CameraRig,
  CoordinateMarkers,
  ElevationContours,
  FlightPath,
  GroundGrid,
  PointCloud,
  Roads,
  SpatialObjects,
} from "@/components/three/SpatialScene";
import { sceneSync } from "@/lib/mockApi";
import { useScrollProgressRef } from "@/lib/useScrollProgressRef";

function DroneFootageInput() {
  const [activeTab, setActiveTab] = useState<"fast_local" | "cloud_3dgs">("fast_local");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedSplat, setSelectedSplat] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "processing" | "completed" | "error">("idle");
  const [progress, setProgress] = useState(0);
  const [stepText, setStepText] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [summary, setSummary] = useState<any>(null);
  const [kaggleReady, setKaggleReady] = useState(false);
  const [kaggleUser, setKaggleUser] = useState("");

  const pollIntervalRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const startPollingStatus = () => {
    stopPolling();
    pollIntervalRef.current = window.setInterval(async () => {
      try {
        const st = await api.fetchPipelineStatus();
        setProgress(st.progress);
        setStepText(st.step);

        if (st.status === "completed") {
          stopPolling();
          setStatus("completed");
          setSummary(st.details);
        } else if (st.status === "error") {
          stopPolling();
          setStatus("error");
          setErrorMsg(st.error || "Reconstruction failed");
        }
      } catch (err: any) {
        console.error("Pipeline polling error:", err);
      }
    }, 1000);
  };

  useEffect(() => {
    api.getKaggleConfig().then((cfg) => {
      setKaggleReady(cfg.configured);
      if (cfg.username) setKaggleUser(cfg.username);
    }).catch(() => {});

    api.fetchPipelineStatus().then((st) => {
      if (st.status === "processing") {
        setStatus("processing");
        setProgress(st.progress);
        setStepText(st.step);
        startPollingStatus();
      } else if (st.status === "completed" && st.details?.manifest) {
        setStatus("completed");
        setSummary(st.details);
      }
    }).catch(() => {});

    return () => stopPolling();
  }, []);

  const acceptVideoFile = (file?: File) => {
    if (file) {
      setSelectedFile(file);
      setStatus("idle");
      setProgress(0);
      setErrorMsg("");
      setSummary(null);
    }
  };

  const acceptSplatFile = (file?: File) => {
    if (file) {
      setSelectedSplat(file);
      setStatus("idle");
      setProgress(0);
      setErrorMsg("");
      setSummary(null);
    }
  };

  const handleStartFastLocal = async () => {
    if (!selectedFile) return;
    setStatus("processing");
    setProgress(5);
    setStepText("Uploading footage for local reconstruction...");
    setErrorMsg("");

    try {
      await api.uploadDroneVideo(selectedFile);
      startPollingStatus();
    } catch (err: any) {
      stopPolling();
      setStatus("error");
      setErrorMsg(err.message || "Failed to initialize fast local pipeline");
    }
  };

  const handleStartKaggle = async () => {
    if (!selectedFile) return;
    setStatus("processing");
    setProgress(5);
    setStepText("Uploading footage and delegating to Kaggle Cloud GPU cluster...");
    setErrorMsg("");

    try {
      await api.uploadDroneVideoKaggle(selectedFile);
      startPollingStatus();
    } catch (err: any) {
      stopPolling();
      setStatus("error");
      setErrorMsg(err.message || "Failed to start Kaggle GPU job");
    }
  };

  const handleImportSplat = async () => {
    if (!selectedSplat) return;
    setStatus("processing");
    setProgress(40);
    setStepText(`Importing trained 3D splat '${selectedSplat.name}'...`);
    setErrorMsg("");

    try {
      const res = await api.importTrainedSplat(selectedSplat);
      setProgress(100);
      setStatus("completed");
      setSummary({
        pipeline_duration_seconds: 1.2,
        buildings_extracted: res.buildings_extracted,
        splat_file: selectedSplat.name,
      });
    } catch (err: any) {
      stopPolling();
      setStatus("error");
      setErrorMsg(err.message || "Failed to import splat file");
    }
  };

  const handleReset = async () => {
    stopPolling();
    try {
      await api.resetPipeline();
    } catch {}
    setStatus("idle");
    setSelectedFile(null);
    setSelectedSplat(null);
    setErrorMsg("");
    setSummary(null);
    setProgress(0);
    setStepText("");
  };

  if (status === "processing") {

    return (
      <div className="pointer-events-auto mx-auto w-full max-w-lg border border-cyan-500/40 bg-background/90 p-4 backdrop-blur-md shadow-[0_0_30px_rgba(6,182,212,0.18)] text-left">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
            <span className="font-mono text-[10px] tracking-[0.2em] text-cyan-400 uppercase font-semibold">
              {activeTab === "fast_local" ? "⚡ Fast Local 3D In Progress" : "☁️ Cloud 3DGS In Progress"}
            </span>
          </div>
          <span className="font-mono text-[11px] font-bold text-cyan-400">{progress}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden bg-muted/40 rounded-full mb-3">
          <div
            className="h-full bg-cyan-400 transition-all duration-500 ease-out shadow-[0_0_12px_#22d3ee]"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="font-mono text-[11px] text-foreground truncate">
          {stepText || "Processing drone footage..."}
        </p>
        <p className="mt-1 font-mono text-[9px] text-muted-foreground uppercase tracking-widest">
          {selectedFile?.name || selectedSplat?.name}
        </p>
      </div>
    );
  }

  if (status === "completed") {
    return (
      <div className="pointer-events-auto mx-auto w-full max-w-lg border border-emerald-500/50 bg-background/90 p-4 backdrop-blur-md shadow-[0_0_30px_rgba(16,185,129,0.18)] text-left">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span className="font-mono text-[10px] tracking-[0.2em] text-emerald-400 uppercase font-semibold">
              3D Digital Twin Ready
            </span>
          </div>
          <span className="font-mono text-[10px] text-muted-foreground">
            {summary?.pipeline_duration_seconds ? `${summary.pipeline_duration_seconds}s` : "Synced"}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 my-3 border-y border-border-strong py-2 text-center">
          <div>
            <div className="font-mono text-[15px] font-bold text-foreground">
              {summary?.buildings_extracted ?? 3}
            </div>
            <div className="font-mono text-[8px] text-muted-foreground uppercase tracking-wider">Buildings</div>
          </div>
          <div>
            <div className="font-mono text-[15px] font-bold text-foreground">
              {summary?.frames_processed ?? 6}
            </div>
            <div className="font-mono text-[8px] text-muted-foreground uppercase tracking-wider">Keyframes</div>
          </div>
          <div>
            <div className="font-mono text-[15px] font-bold text-cyan-400">PostGIS</div>
            <div className="font-mono text-[8px] text-muted-foreground uppercase tracking-wider">3D Solids</div>
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 mt-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="h-8 rounded-none border border-border-strong font-mono text-[9px] uppercase tracking-wider hover:bg-muted"
          >
            <RotateCcw className="h-3 w-3 mr-1.5" />
            Reset
          </Button>
          <Button
            asChild
            size="sm"
            className="h-8 rounded-none bg-cyan-500 hover:bg-cyan-400 text-black font-mono text-[10px] font-bold tracking-[0.14em] uppercase shadow-[0_0_15px_rgba(6,182,212,0.4)]"
          >
            <a href="/demo">
              Launch 3D Twin
              <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
            </a>
          </Button>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="pointer-events-auto mx-auto w-full max-w-lg border border-red-500/50 bg-background/90 p-4 text-left shadow-[0_0_20px_rgba(239,68,68,0.2)]">
        <div className="flex items-center gap-2 mb-2 text-red-400">
          <AlertTriangle className="h-4 w-4" />
          <span className="font-mono text-[10px] tracking-wider uppercase font-semibold">
            Pipeline Processing Error
          </span>
        </div>
        <p className="font-mono text-[11px] text-muted-foreground mb-3">{errorMsg}</p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            className="h-7 rounded-none border-border-strong font-mono text-[9px] uppercase hover:bg-muted"
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            Reset
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              stopPolling();
              setStatus("idle");
              setErrorMsg("");
            }}
            className="h-7 rounded-none border-border-strong font-mono text-[9px] uppercase hover:bg-muted"
          >
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="pointer-events-auto mx-auto w-full max-w-lg space-y-2">
      {/* Mode Selector Tabs */}
      <div className="flex border border-border-strong bg-background/80 p-0.5">
        <button
          onClick={() => setActiveTab("fast_local")}
          className={`flex-1 py-1.5 font-mono text-[10px] tracking-[0.14em] uppercase flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "fast_local"
              ? "bg-cyan-500 text-black font-bold shadow-[0_0_10px_rgba(6,182,212,0.3)]"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Zap className="h-3.5 w-3.5" />
          ⚡ Fast Local 3D (~25s)
        </button>
        <button
          onClick={() => setActiveTab("cloud_3dgs")}
          className={`flex-1 py-1.5 font-mono text-[10px] tracking-[0.14em] uppercase flex items-center justify-center gap-1.5 transition-colors ${
            activeTab === "cloud_3dgs"
              ? "bg-cyan-500 text-black font-bold shadow-[0_0_10px_rgba(6,182,212,0.3)]"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Cloud className="h-3.5 w-3.5" />
          ☁️ High-Fidelity 3DGS
        </button>
      </div>

      {/* Tab 1: Fast Local 3D Depth Reconstruction */}
      {activeTab === "fast_local" && (
        <div className="space-y-2">
          <div
            onDragEnter={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              acceptVideoFile(e.dataTransfer.files[0]);
            }}
            className={`flex w-full items-center justify-between gap-4 border px-4 py-3 text-left transition-colors ${
              dragging ? "border-accent bg-accent/10" : "border-border-strong bg-background/70"
            }`}
          >
            <div className="flex min-w-0 items-center gap-3">
              <Upload aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />
              <div className="min-w-0">
                <p className="truncate font-mono text-[10px] tracking-[0.18em] text-foreground uppercase">
                  {selectedFile ? selectedFile.name : "Drop drone footage (MP4 / MOV)"}
                </p>
                <p className="mt-1 font-mono text-[9px] tracking-[0.16em] text-muted-foreground uppercase">
                  {selectedFile
                    ? `${(selectedFile.size / 1024 / 1024).toFixed(1)} MB • Real 3D depth unprojection ready`
                    : "Instant local GPU reconstruction"}
                </p>
              </div>
            </div>
            <Button
              asChild
              variant="outline"
              size="sm"
              className="h-8 shrink-0 rounded-none border-border-strong bg-transparent px-3 font-mono text-[9px] tracking-[0.14em] uppercase shadow-none hover:border-accent hover:bg-accent hover:text-accent-foreground"
            >
              <label>
                Browse
                <input
                  type="file"
                  accept="video/mp4,video/quicktime,.mov,.avi,.mkv"
                  onChange={(e) => acceptVideoFile(e.target.files?.[0])}
                  className="sr-only"
                />
              </label>
            </Button>
          </div>

          {selectedFile && (
            <Button
              onClick={handleStartFastLocal}
              className="w-full h-9 rounded-none bg-cyan-500 hover:bg-cyan-400 text-black font-mono text-[10px] font-bold tracking-[0.16em] uppercase shadow-[0_0_20px_rgba(6,182,212,0.35)] flex items-center justify-center gap-2"
            >
              <Zap className="h-3.5 w-3.5 fill-black" />
              Build Real 3D Twin Locally (~25s)
            </Button>
          )}
        </div>
      )}

      {/* Tab 2: High-Fidelity 3DGS Cloud (Kaggle & Colab) */}
      {activeTab === "cloud_3dgs" && (
        <div className="space-y-3">
          {/* Section A: Automated Kaggle GPU Runner */}
          <div className="border border-border-strong bg-background/70 p-3 text-left space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] tracking-wider text-cyan-400 uppercase font-semibold flex items-center gap-1.5">
                <Cloud className="h-3.5 w-3.5" />
                1. Automated Kaggle 16GB GPU Job
              </span>
              <span className="font-mono text-[9px] text-muted-foreground uppercase">
                {kaggleReady ? `✓ API Ready${kaggleUser ? ` (${kaggleUser})` : ""}` : "Requires .env keys"}
              </span>
            </div>
            <p className="font-mono text-[9px] text-muted-foreground">
              Dispatches 3DGS training to Kaggle's cloud GPU and auto-downloads the scene.
            </p>
            <div className="flex gap-2">
              <Button
                asChild
                variant="outline"
                size="sm"
                className="h-8 flex-1 rounded-none border-border-strong text-[9px] font-mono uppercase hover:border-cyan-400"
              >
                <label>
                  {selectedFile ? selectedFile.name : "Select Video"}
                  <input
                    type="file"
                    accept="video/mp4,video/quicktime,.mov"
                    onChange={(e) => acceptVideoFile(e.target.files?.[0])}
                    className="sr-only"
                  />
                </label>
              </Button>
              <Button
                onClick={handleStartKaggle}
                disabled={!selectedFile}
                size="sm"
                className="h-8 rounded-none bg-cyan-500 hover:bg-cyan-400 text-black font-mono text-[9px] uppercase font-bold px-3 disabled:opacity-50"
              >
                Run on Kaggle
              </Button>
            </div>
          </div>

          {/* Section B: Colab Notebook & Splat Import */}
          <div className="border border-border-strong bg-background/70 p-3 text-left space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] tracking-wider text-foreground uppercase font-semibold flex items-center gap-1.5">
                <FileCode className="h-3.5 w-3.5 text-accent" />
                2. Import Trained .splat / Colab
              </span>
              <a
                href="https://colab.research.google.com/"
                target="_blank"
                rel="noreferrer"
                className="font-mono text-[9px] text-cyan-400 hover:underline flex items-center gap-1 uppercase"
              >
                Colab Notebook
                <ExternalLink className="h-2.5 w-2.5" />
              </a>
            </div>
            <div className="flex gap-2">
              <Button
                asChild
                variant="outline"
                size="sm"
                className="h-8 flex-1 rounded-none border-border-strong text-[9px] font-mono uppercase hover:border-accent"
              >
                <label>
                  {selectedSplat ? selectedSplat.name : "Browse .splat / .ply"}
                  <input
                    type="file"
                    accept=".splat,.ply"
                    onChange={(e) => acceptSplatFile(e.target.files?.[0])}
                    className="sr-only"
                  />
                </label>
              </Button>
              <Button
                onClick={handleImportSplat}
                disabled={!selectedSplat}
                size="sm"
                className="h-8 rounded-none bg-accent hover:bg-accent/80 text-accent-foreground font-mono text-[9px] uppercase font-bold px-3 disabled:opacity-50"
              >
                Import 3DGS
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function Hero() {
  const section = useRef<HTMLElement>(null);
  const { progress, scrollYProgress } = useScrollProgressRef(section, [
    "start start",
    "end start",
  ]);

  const headlineY = useTransform(scrollYProgress, [0, 1], ["0%", "-140%"]);
  const headlineOpacity = useTransform(scrollYProgress, [0, 0.55], [1, 0]);
  const copyOpacity = useTransform(scrollYProgress, [0, 0.3], [1, 0]);

  return (
    <section ref={section} id="top" className="relative h-[220vh]">
      <div className="sticky top-0 h-screen overflow-hidden">
        <SceneCanvas
          className="absolute inset-0"
          camera={{ position: [0, 8, 24], fov: 44 }}
        >
          <CameraRig progressRef={progress} from={[0, 9, 26]} to={[0, 3.6, 11]} />
          <GroundGrid />
          <PointCloud progressRef={progress} count={4200} />
          <ElevationContours progressRef={progress} />
          <Roads progressRef={progress} />
          <CoordinateMarkers />
          <FlightPath />
          <SpatialObjects objects={sceneSync.objects} progressRef={progress} />
        </SceneCanvas>

        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_35%,transparent_25%,var(--background)_92%)]" />

        <div className="relative mx-auto h-full max-w-[1400px] px-6 lg:px-10">
          <motion.div
            style={{ y: headlineY, opacity: headlineOpacity }}
            className="absolute top-1/2 left-1/2 w-[min(94vw,980px)] -translate-x-1/2 -translate-y-1/2 text-center"
          >
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, delay: 0.2 }}
              className="label-tech"
            >
              AI-Powered 3D Spatial Intelligence
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 26, filter: "blur(10px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ duration: 1.2, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="mt-6 font-display text-[clamp(3.25rem,7.4vw,7rem)] leading-[0.88] font-normal"
            >
              Turn one
              <br />
              <span>drone pass</span>
              <br />
              <span className="text-muted-foreground">into </span>
              <span className="text-accent">spatial intelligence.</span>
            </motion.h1>

            <div className="mt-8">
              <DroneFootageInput />
            </div>
          </motion.div>

          <motion.div
            style={{ opacity: copyOpacity }}
            className="absolute right-6 bottom-24 left-6 flex flex-col gap-6 md:flex-row md:items-end md:justify-between lg:right-10 lg:left-10"
          >
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
              Transform a single aerial capture into an interactive digital twin
              that can be measured, queried and explored.
            </p>

            <div className="flex flex-wrap items-center gap-4">
              <a
                href="#platform"
                className="group flex items-center gap-3 bg-accent px-6 py-3 font-mono text-[11px] tracking-[0.18em] text-accent-foreground uppercase transition-opacity hover:opacity-90"
              >
                Explore the platform
                <span className="h-px w-5 bg-accent-foreground transition-all group-hover:w-8" />
              </a>
              <a
                href="#reconstruction"
                className="border border-border-strong px-6 py-3 font-mono text-[11px] tracking-[0.18em] text-foreground uppercase transition-colors hover:border-accent hover:text-accent"
              >
                See how it works
              </a>
            </div>
          </motion.div>

          <div className="absolute right-6 bottom-6 left-6 hidden grid-cols-4 gap-6 border-t border-border pt-5 md:grid lg:right-10 lg:left-10">
            {[
              ["47.6205° N", "Latitude"],
              ["122.3493° W", "Longitude"],
              ["118 M", "Altitude"],
              ["8.4 M", "Points"],
            ].map(([value, label]) => (
              <div key={label}>
                <p className="font-mono text-xs text-foreground">{value}</p>
                <p className="label-tech mt-1">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
