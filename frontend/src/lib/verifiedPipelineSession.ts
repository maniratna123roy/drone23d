import type { GaussianData } from "../components/three/gaussian-data.ts";
import type { PipelineStatus, VerifiedSceneManifest } from "../types/spatial.ts";
import type { VerifiedPipelineApi } from "./verifiedPipeline.ts";

export interface LoadedVerifiedScene {
  manifest: VerifiedSceneManifest;
  data: GaussianData;
}
export interface VerifiedPipelineState {
  status: PipelineStatus | null;
  manifest: VerifiedSceneManifest | null;
  displayed: LoadedVerifiedScene | null;
  checking: boolean;
  uploading: boolean;
  loadingAssets: boolean;
  connectionError: string | null;
  uploadError: string | null;
  assetError: string | null;
}
export const initialPipelineState: VerifiedPipelineState = {
  status: null,
  manifest: null,
  displayed: null,
  checking: true,
  uploading: false,
  loadingAssets: false,
  connectionError: null,
  uploadError: null,
  assetError: null,
};
export function manifestKey(manifest: VerifiedSceneManifest): string {
  const q = manifest.capabilities?.queries ? "q1" : "q0";
  const e = manifest.capabilities?.edits ? "e1" : "e0";
  const splatSha = manifest.sha256?.["scene.splat"] ?? "";
  return `${manifest.job_id}:${manifest.version}:${manifest.semantics}:${manifest.coordinate_frame}:${q}:${e}:${splatSha}`;
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : "An unexpected pipeline request failed.";
}

/** Owns request lifetimes and atomic scene replacement; no scene is inferred from job completion. */
export class VerifiedPipelineSession {
  state: VerifiedPipelineState = { ...initialPipelineState };
  private active = false;
  private polling: ReturnType<typeof setInterval> | null = null;
  private refreshRequest: AbortController | null = null;
  private assetRequest: AbortController | null = null;
  private uploadRequest: AbortController | null = null;
  private refreshPromise: Promise<void> | null = null;
  private retryQueued = false;
  private statusRevision = 0;
  private attemptedManifest: string | null = null;
  private api: VerifiedPipelineApi;
  private onChange: (state: VerifiedPipelineState) => void;

  constructor(api: VerifiedPipelineApi, onChange: (state: VerifiedPipelineState) => void) {
    this.api = api;
    this.onChange = onChange;
  }
  private patch(patch: Partial<VerifiedPipelineState>) {
    if (!this.active) return;
    this.state = { ...this.state, ...patch };
    this.onChange(this.state);
  }
  start(pollMs = 2000) {
    if (this.active) return;
    this.active = true;
    void this.refresh();
    this.polling = setInterval(() => void this.refresh(), pollMs);
  }
  stop() {
    this.active = false;
    if (this.polling) clearInterval(this.polling);
    this.polling = null;
    this.refreshRequest?.abort();
    this.assetRequest?.abort();
    this.uploadRequest?.abort();
  }
  refresh(retryAssets = false): Promise<void> {
    if (!this.active) return Promise.resolve();
    if (this.refreshPromise) {
      this.retryQueued ||= retryAssets;
      return this.refreshPromise;
    }
    if (retryAssets) this.patch({ connectionError: null, assetError: null });
    const controller = new AbortController();
    this.refreshRequest = controller;
    const revision = this.statusRevision;
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]);
    this.refreshPromise = (async () => {
      const [status, scene] = await Promise.allSettled([
        this.api.status(signal),
        this.api.scene(signal),
      ]);
      if (!this.active || controller.signal.aborted) return;
      const failures: string[] = [];
      if (status.status === "fulfilled") {
        if (revision === this.statusRevision && !this.state.uploading)
          this.patch({ status: status.value });
      } else failures.push(message(status.reason));
      if (scene.status === "fulfilled") {
        if (scene.value.status === "empty") {
          this.assetRequest?.abort();
          this.attemptedManifest = null;
          // An explicit empty publication is authoritative, not a license to use old static assets.
          this.patch({ manifest: null, displayed: null, loadingAssets: false, assetError: null });
        } else {
          this.patch({ manifest: scene.value.manifest });
          this.loadScene(scene.value.manifest, retryAssets);
        }
      } else failures.push(message(scene.reason));
      this.patch({
        checking: false,
        ...(failures.length ? { connectionError: failures.join(" ") } : {}),
      });
    })().finally(() => {
      this.refreshPromise = null;
      if (this.retryQueued && this.active) {
        this.retryQueued = false;
        void this.refresh(true);
      }
    });
    return this.refreshPromise;
  }
  private loadScene(manifest: VerifiedSceneManifest, retry: boolean) {
    const key = manifestKey(manifest);
    if (this.state.displayed && manifestKey(this.state.displayed.manifest) === key) return;
    if (!retry && this.attemptedManifest === key) return;
    this.attemptedManifest = key;
    this.assetRequest?.abort();
    const controller = new AbortController();
    this.assetRequest = controller;
    this.patch({ loadingAssets: true, assetError: null });
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(120000)]);
    void this.api
      .assets(manifest, signal)
      .then((data) => {
        if (
          !this.active ||
          controller.signal.aborted ||
          this.state.manifest === null ||
          manifestKey(this.state.manifest) !== key
        )
          return;
        this.patch({ displayed: { manifest, data }, loadingAssets: false, assetError: null });
      })
      .catch((error: unknown) => {
        if (!this.active || controller.signal.aborted) return;
        this.patch({
          loadingAssets: false,
          assetError: `Could not display verified version ${manifest.version}: ${message(error)}`,
        });
      });
  }
  async upload(file: File): Promise<void> {
    if (!this.active || this.state.uploading || this.state.status?.status === "processing") return;
    const controller = new AbortController();
    this.uploadRequest = controller;
    this.statusRevision++;
    this.patch({ uploading: true, uploadError: null });
    try {
      const accepted = await this.api.upload(file, controller.signal);
      if (!this.active || controller.signal.aborted) return;
      this.statusRevision++;
      this.patch({
        status: {
          job_id: accepted.job_id,
          status: "processing",
          step: accepted.message,
          progress: 0,
          details: {},
          error: null,
        },
      });
    } catch (error: unknown) {
      if (!this.active || controller.signal.aborted) return;
      this.patch({ uploadError: message(error) });
    } finally {
      if (this.active && !controller.signal.aborted) {
        this.patch({ uploading: false });
        void this.refresh();
      }
    }
  }
}
