import React, { useState, useEffect } from "react";
import {
  Cpu,
  Wifi,
  WifiOff,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Settings2,
  Key,
  Sparkles,
  Zap,
  HelpCircle,
  ShieldCheck,
} from "lucide-react";

interface ColabStatus {
  connected: boolean;
  url?: string;
  device?: string;
  vram_gb?: number;
  model_ready?: boolean;
  error?: string;
}

interface ColabWorkerPanelProps {
  onStatusChange?: (status: ColabStatus) => void;
}

export const ColabWorkerPanel: React.FC<ColabWorkerPanelProps> = ({
  onStatusChange,
}) => {
  const [workerUrl, setWorkerUrl] = useState<string>(() => {
    return localStorage.getItem("spatial_twin_cloud_url") || "";
  });
  const [apiKey, setApiKey] = useState<string>(() => {
    return localStorage.getItem("spatial_twin_cloud_api_key") || "";
  });
  const [status, setStatus] = useState<ColabStatus>({ connected: false });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);

  // Check initial connection status on backend
  useEffect(() => {
    const fetchInitialStatus = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8001/v1/colab/status");
        if (res.ok) {
          const data: ColabStatus = await res.json();
          setStatus(data);
          if (data.url) {
            setWorkerUrl(data.url);
            localStorage.setItem("spatial_twin_cloud_url", data.url);
          }
          onStatusChange?.(data);
        }
      } catch {
        // Backend sidecar starting up
      }
    };
    fetchInitialStatus();
  }, [onStatusChange]);

  const handleConnect = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!workerUrl.trim()) {
      setError("Please enter your Cloud GPU endpoint URL or Cloudflare Tunnel URL.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://127.0.0.1:8001/v1/colab/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ worker_url: workerUrl.trim() }),
      });

      if (res.ok) {
        const data: ColabStatus = await res.json();
        setStatus(data);
        setError(null);
        localStorage.setItem("spatial_twin_cloud_url", workerUrl.trim());
        if (apiKey.trim()) {
          localStorage.setItem("spatial_twin_cloud_api_key", apiKey.trim());
        }
        onStatusChange?.(data);
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(
          errData.detail ||
            "Could not connect to Cloud GPU worker. Please verify the URL and ensure the server is running."
        );
        setStatus({ connected: false });
      }
    } catch (err: any) {
      setError("Backend connection failed: " + err.message);
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await fetch("http://127.0.0.1:8001/v1/colab/disconnect", { method: "POST" });
    } catch {}
    setStatus({ connected: false });
    setError(null);
    onStatusChange?.({ connected: false });
  };

  return (
    <div className="rounded-xl border border-border/80 bg-card/60 backdrop-blur-md shadow-sm transition-all overflow-hidden">
      {/* Sleek, Non-Intrusive Compute Engine Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-3">
          <div
            className={`h-8 w-8 rounded-lg flex items-center justify-center border transition-colors ${
              status.connected
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                : "bg-purple-500/10 border-purple-500/20 text-purple-400"
            }`}
          >
            {status.connected ? <Zap className="h-4 w-4" /> : <Cpu className="h-4 w-4" />}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-foreground tracking-tight">
                Reconstruction Engine:
              </span>
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono font-medium border ${
                  status.connected
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : "bg-blue-500/10 text-blue-300 border-blue-500/30"
                }`}
              >
                {status.connected ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Cloud GPU Active • {status.device || "Tesla T4"} ({status.vram_gb || 15} GB)</span>
                  </>
                ) : (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                    <span>Smart Hybrid Engine Active (Automatic Local & Cloud Fallback)</span>
                  </>
                )}
              </span>
            </div>

            <p className="text-[11px] text-muted-foreground mt-0.5">
              {status.connected
                ? "Uploaded videos are automatically routed to the Cloud GPU for accelerated deep SfM & meshing."
                : "Zero configuration needed. Upload your drone video below to automatically generate your 3D digital twin."}
            </p>
          </div>
        </div>

        {/* Action Button: Optional Cloud GPU Settings */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setDrawerOpen(!drawerOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono border border-border/80 bg-background/80 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            <Settings2 className="h-3.5 w-3.5 text-purple-400" />
            <span>Cloud GPU & API Keys</span>
            {drawerOpen ? (
              <ChevronUp className="h-3 w-3 ml-0.5" />
            ) : (
              <ChevronDown className="h-3 w-3 ml-0.5" />
            )}
          </button>
        </div>
      </div>

      {/* Expandable Advanced Cloud GPU Settings Drawer */}
      {drawerOpen && (
        <div className="border-t border-border/60 bg-muted/20 p-4 sm:p-5 space-y-4">
          {/* Informational Guidance on Colab & API Keys */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg border border-purple-500/20 bg-purple-950/15 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-purple-300">
                <HelpCircle className="h-4 w-4 text-purple-400" />
                <span>About Google Colab & API Keys</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Consumer Google Colab does not offer public API keys for headless triggers (Google requires a browser session). However, running Cell 8 once in Colab auto-registers the GPU worker with zero manual copy-pasting required thereafter!
              </p>
            </div>

            <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-950/15 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-emerald-300">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <span>Dedicated Cloud GPU / Vertex AI</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                For complete automation with zero browser tabs, you can connect Google Cloud Vertex AI, RunPod, or a dedicated GPU server using a permanent endpoint URL or API key below.
              </p>
            </div>
          </div>

          {/* Connection Controls */}
          {status.connected ? (
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-xs font-mono">
              <div className="flex items-center gap-2 text-emerald-300">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                <span>
                  Connected to Cloud GPU: <strong>{status.url}</strong>
                </span>
              </div>
              <button
                type="button"
                onClick={handleDisconnect}
                className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors"
              >
                Disconnect
              </button>
            </div>
          ) : (
            <form onSubmit={handleConnect} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-muted-foreground">
                    Cloud GPU Worker URL (Colab Tunnel or Cloud Server):
                  </label>
                  <input
                    type="url"
                    placeholder="https://xxxx.trycloudflare.com or https://api.runpod.ai"
                    value={workerUrl}
                    onChange={(e) => setWorkerUrl(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-background border border-border text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-mono text-muted-foreground">
                    Cloud GPU API Key (Optional for Vertex AI / RunPod):
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      placeholder="Optional API token (e.g. gcp_... or rpa_...)"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-background border border-border text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-purple-500"
                    />
                    <Key className="absolute right-3 top-2.5 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex items-center gap-2">
                  <a
                    href="https://colab.research.google.com"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-mono text-purple-400 hover:text-purple-300 underline underline-offset-2"
                  >
                    <span>Open pipeline/videogrammetry_colab_training.ipynb</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono font-medium transition-colors disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Testing Cloud GPU...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="h-3.5 w-3.5" />
                      <span>Save & Connect Cloud GPU</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {error && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-destructive/15 border border-destructive/40 text-destructive text-xs font-mono">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <p>{error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
