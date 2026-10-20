# Videogrammetry Sidecar: System Architecture

A non-invasive, side-by-side video-to-3D reconstruction system to run next to a live project without modifying any of its code.

## 1. Purpose and ground rules

This design builds a drone-video-to-3D subsystem modeled on what Skyebrowse publicly states about its approach: videogrammetry from one continuous video, optional GPS file, no ground control points, cloud automation, resolution tiers, an AI quality check that redoes poor models, and mesh / point cloud / orthomosaic outputs (not Gaussian splats). Skyebrowse publishes no internals, so the stages below are standard structure-from-motion (SfM) and multi-view stereo (MVS) engineering, not a copy of their code.

**Hard constraints**

- Zero edits to the host project: no source, config, migration, dependency or CI changes.
- Additive only: own repo, own containers, own database, own storage prefix.
- Removable: stopping the sidecar returns the host to its exact prior state.
- Integration only through interfaces the host already exposes (HTTP, storage events, webhooks, read-only DB access, links or iframes).

## 2. Integration strategy (how it runs beside the host untouched)

The pattern is a **sidecar with an anti-corruption layer**. Only one package (`adapters/host_<name>/`) knows the host's data shapes; the rest of the sidecar is host-agnostic.

| Mode | How it works | Host change needed |
| --- | --- | --- |
| A. Gateway route | Reverse proxy or load balancer sends `/3d/*` to the sidecar | Infra routing only, no app code |
| B. Storage-event tap | Sidecar subscribes to bucket or folder notifications (S3 event, MinIO webhook, inotify) and picks up new videos | None |
| C. Webhook or poll adapter | Sidecar consumes the host's existing webhooks or polls its public API | None |
| D. Read-only data access | Separate DB role with SELECT on agreed views, or CDC replication into the sidecar | None (new read-only role) |
| E. Viewer embed | Sidecar hosts the 3D viewer; host links to it or iframes it | None, or a link added by the host team later |

**Recommended default: A + B + E.** C and D only if the host has no usable storage events.

**Isolation rules**

- Separate database (or at minimum a separate schema `vg_*` with its own role). The sidecar never writes to host tables.
- Separate bucket or prefix with its own credentials. Host storage is accessed read-only.
- Own Kubernetes namespace or compose project, with CPU/RAM/GPU limits so reconstruction can never starve the host.
- **Shadow mode first**: process real uploads, show results to nobody, compare quality. Then enable via a gateway-level flag.
- Kill switch: remove the gateway route and stop the event subscription. Nothing else to undo.

## 3. High-level architecture

```
 Host project (untouched)                  Sidecar (new, isolated)
 +--------------------+  storage event  +----------------------------------------------+
 | existing app / API |---------------->| Ingest Adapter -> Capture API (FastAPI)       |
 | existing storage   |  or /3d/* proxy |        |                                      |
 +--------------------+                 |        v                                      |
        ^  webhook / link / iframe       |  Orchestrator (Postgres jobs + Redis queue)   |
        |<-------------------------------|        |                                      |
                                         |  +-----+-------+-----------+----------+       |
                                         |  v             v           v          v       |
                                         | CPU workers  GPU workers  GPU workers Export  |
                                         | (probe,      (poses/SfM)  (dense,     workers |
                                         |  frames)                  mesh,tex)           |
                                         |        \         |          /          |      |
                                         |         +--> Quality Gate --retry--+          |
                                         |  Object store: raw / frames / work / out      |
                                         |  Viewer + tile server | Metrics, logs, traces |
                                         +----------------------------------------------+
```

## 4. Components

1. **Ingest Adapter**: translates a host event (new video object, webhook, API call) into a neutral `CaptureRequest`. Idempotent on `(source_system, source_id, content_hash)`.
2. **Capture API (FastAPI)**: public interface of the sidecar. Creates captures, issues resumable upload URLs (S3 multipart or tus), reports job status, serves signed artifact URLs.
3. **Orchestrator**: stage-by-stage state machine. Simple option: Postgres job tables plus Redis and Celery/RQ. If you want durable retries and visibility out of the box, use Temporal. Start simple; the stage interface below keeps both options open.
4. **CPU workers**: probe, frame extraction and selection, exports, orthomosaic rendering.
5. **GPU workers**: feature matching, SfM, dense reconstruction, texturing. One job per GPU at a time.
6. **Quality Gate**: computes metrics after poses and after meshing, decides pass, retry with a different strategy, or ship as degraded.
7. **Artifact store**: S3-compatible (MinIO for dev). Layout: `raw/`, `frames/`, `work/`, `out/` under `captures/{capture_id}/`.
8. **Viewer and tile service**: serves GLB or 3D Tiles and the orthomosaic (COG) to a web viewer with measurement tools.
9. **Observability stack**: Prometheus metrics, structured logs, OpenTelemetry traces, per-stage dashboards.

## 5. Reconstruction pipeline (stage by stage)

Every stage is a pure function: `inputs (artifact refs) + params -> outputs (artifact refs) + metrics`. Outputs are content-addressed so a retry or a crash resumes from the last good stage.

### Stage 0: Validate and probe (CPU)

- `ffprobe` for codec, resolution, fps, duration, rotation, color space.
- Extract embedded telemetry: DJI `.SRT` or MP4 data track via `exiftool -ee`, plus an optional uploaded GPS file. Store as a per-frame timeline (lat, lon, alt, gimbal if present).
- Reject or warn on: under 20 s, heavy rolling-shutter jitter, extreme motion blur, missing video stream.

### Stage 1: Frame extraction and selection (CPU)

- Decode with ffmpeg (hardware decode if available).
- Score each frame for sharpness (variance of Laplacian) and discard the blurriest percentile.
- Select keyframes by **parallax, not fixed interval**: keep a frame when median feature displacement from the last kept frame reaches roughly 3 to 5 percent of image width. This gives 70 to 90 percent overlap regardless of drone speed.
- Typical outcome: a 2-minute 4K clip (about 3,600 frames) reduces to 300 to 800 frames. Higher tiers keep more frames and full resolution.
- Optional: undistort using the camera's lens profile when known.

### Stage 2: Dynamic-object masking (GPU, premium tiers)

- Run an instance segmenter (people, vehicles, birds) per selected frame and write masks.
- Masks are passed into feature extraction so moving objects never produce matches. This mirrors the AI moving-object removal that Skyebrowse lists for its top tier.

### Stage 3: Pose estimation / SfM (GPU)

- Primary: COLMAP with **sequential matching plus loop closure** (video frames are ordered, so matching is a sliding window of about 10 to 20 neighbors plus vocabulary-tree retrieval for revisits). This is far cheaper than exhaustive matching.
- Alternative for speed on larger sets: GLOMAP (global SfM) fed by the same matches.
- Fallback for hard footage (low texture, fast motion): a SLAM-style tracker to seed poses, then bundle adjustment.
- **GPS as a prior**: use per-frame GPS to initialize and constrain, then apply a robust similarity transform (Umeyama with RANSAC) from SfM camera centers to a local ENU or UTM frame. This provides metric scale and georeferencing without ground control points.
- Honest limit: with consumer GPS (meters of error) relative accuracy is excellent but absolute accuracy is meters unless the drone logs RTK/PPK. State this in the output metadata.

### Stage 4: Dense reconstruction (GPU)

- Multi-view stereo: depth map per frame, geometric consistency filtering, fusion to a dense point cloud (COLMAP patch-match or OpenMVS).
- Tile the scene into blocks (for example 200 m or about 2 GB of points per block) so VRAM and RAM stay bounded and blocks can run in parallel.
- Optional for weak-texture regions (water, roofs, sky edges): use a monocular depth model as a soft prior to guide fusion, never as ground truth.
- Output: dense colored point cloud per tile.

### Stage 5: Mesh and texture (GPU/CPU)

- Surface reconstruction (Delaunay-based in OpenMVS, or Poisson in Open3D for smaller scenes), hole filling, decimation to per-tier triangle budgets.
- Texture: project source frames onto the mesh with view selection and seam leveling, producing atlases (4K or 8K tiles).
- Generate LODs with meshoptimizer for fast web loading.

### Stage 6: Georeferenced products (CPU)

- **LAZ** point cloud via PDAL or laspy, in the chosen CRS.
- **Orthomosaic**: render the textured mesh orthographically top-down at the target ground sample distance, write Cloud-Optimized GeoTIFF with GDAL or rasterio.
- **DSM** (optional): rasterize the point cloud heights for volume and cut-fill tools.

### Stage 7: Quality gate (the automated redo loop)

Metrics computed and stored in `quality_reports`:

| Metric | Starting threshold (calibrate on your data) |
| --- | --- |
| Registered frames / selected frames | at least 0.85 |
| Mean reprojection error | at most 1.0 px |
| Sparse points per registered image | above a floor tied to resolution |
| Mesh hole area ratio | under 2 percent |
| Held-out view check: render the mesh at withheld camera poses, compare with the real frame (SSIM and LPIPS) | SSIM at least 0.7, calibrate |
| Outlier / floating geometry ratio | under 1 percent |

**Retry ladder (max 3 attempts):**

1. More frames and a wider matching window.
2. Enable dynamic-object masks if not already on.
3. Higher feature resolution or a different matcher, then rebuild.
4. Ship the best attempt flagged `degraded` with the failing metrics visible.

Optional extra check: send 4 to 6 rendered views to a vision model with a rubric (holes, melted edges, floating blobs) and add its verdict as a soft signal. Keep it advisory so the pipeline stays deterministic.

### Stage 8: Export and publish (CPU)

- GLB (via gltf-transform with meshopt or Draco), OBJ with MTL, USDZ (Blender headless or a USD toolchain), LAZ, COG GeoTIFF.
- For large scenes, generate **3D Tiles** so the viewer streams by level of detail.
- Write a `manifest.json` per capture: inputs, parameters, tool versions, metrics, CRS, accuracy notes. This is also your reproducibility and audit record.

## 6. Quality tiers (configuration, not code branches)

| Tier | Frame budget | Internal resolution | Masks | QA retries | Intended output |
| --- | --- | --- | --- | --- | --- |
| Lite | about 200 | 1080p-class | off | 0 | quick preview, coarse mesh |
| Standard | about 400 | 4K | off | 1 | operational documentation |
| Premium | about 700 | 4K to 8K | on | 2 | measurement-grade mesh and cloud |
| Premium Advanced | up to 1,500 | 8K and above, tiled | on | 3 | maximum detail, automatic redo loop |

Tiers are YAML profiles consumed by the same pipeline, so adding a tier is a config change.

## 7. Data model (sidecar-owned)

- `captures(id, source_system, source_id, content_hash, tier, status, crs, created_at)`
- `jobs(id, capture_id, attempt, status, started_at, finished_at, worker_id)`
- `job_stages(job_id, stage, status, params_json, metrics_json, started_at, finished_at, error)`
- `artifacts(id, capture_id, kind, uri, sha256, bytes, produced_by_stage)`
- `quality_reports(job_id, metrics_json, verdict, retry_strategy)`
- `webhooks(id, target_url, secret_ref, events)` and `webhook_deliveries(...)`

Use your own database instance or at least a dedicated schema and role. Never share tables with the host.

## 8. API contract (stable, versioned)

```
POST /v1/captures              -> 201 { capture_id, upload: { url, method, headers } }
PUT  {upload.url}              -> resumable upload of the video
POST /v1/captures/{id}/start   { tier, gps_file_ref?, crs? }
GET  /v1/captures/{id}         -> { status, stage, progress, attempt, quality }
GET  /v1/captures/{id}/artifacts -> signed URLs for glb, obj, usdz, laz, cog
POST /v1/webhooks              -> register callback (HMAC-SHA256 signed)
```

Completion webhook payload:

```
{ event: capture.completed, capture_id, source_id, status: ok|degraded|failed,
  tier, artifacts: [{kind, url, bytes}], quality: {...}, viewer_url }
```

Rules: idempotency keys on every POST, signed payloads, timestamp and replay protection, semantic versioning on `/v1`.

## 9. Deployment

**Dev**: Docker Compose with API, worker (CPU), worker (GPU), Postgres, Redis, MinIO, viewer, Prometheus.

**Prod**: Kubernetes (or a single GPU VM to start) in its own namespace.

- Separate node pools: CPU pool and GPU pool (24 GB VRAM class: L4, A10G, RTX 4090, or better).
- Autoscale GPU workers on queue depth (KEDA); scale to zero when idle.
- Spot or preemptible GPUs are fine because stages are idempotent and checkpointed.
- Scratch: fast local NVMe (several hundred GB) per GPU worker; artifacts promoted to object storage between stages.
- Rough sizing per worker: 16+ CPU cores, 64 GB RAM, one 24 GB GPU. Treat processing time as roughly 1x to 3x video length for standard tiers on this class and measure it yourself; it varies strongly with scene size and footage quality.

## 10. Reliability

- Stages are idempotent and keyed by input hashes; re-running a finished stage is a no-op.
- Per-stage timeouts, memory limits, and a dead-letter queue with the manifest attached for debugging.
- Poison-input guard: after N failures the capture is quarantined and the webhook reports `failed` with reasons.
- Back-pressure: cap concurrent captures per tenant; reject uploads above size or duration limits early.
- Retention policy: delete `frames/` and `work/` after success (keep `raw/` and `out/` per policy), which controls most storage cost.

## 11. Security and privacy

- Presigned, short-lived URLs only; no public buckets.
- Per-tenant prefixes and row-level checks on every API call.
- Secrets in a secret manager, never in the host repo or environment dumps.
- Drone video can contain faces and license plates: offer an optional blur or removal pass in Stage 2 and document retention.
- Pin and scan all container images; third-party reconstruction binaries run without network access.

## 12. Observability

- Metrics: queue depth, stage duration histograms, GPU utilization, retry rate, degraded rate, cost per capture.
- Logs: structured JSON with `capture_id`, `job_id`, `stage`.
- Traces: one trace per capture across all stages.
- Alerts: stuck jobs, rising degraded rate, GPU OOM, storage growth.
- A **benchmark set** of 5 to 10 known videos run on every release to catch quality regressions.

## 13. Rollout plan

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| 0. Spike | One video, CLI only: frames, COLMAP, dense, mesh, GLB | A viewable model and recorded metrics |
| 1. Pipeline | Orchestrator, stage contracts, QA metrics, artifacts | Benchmark set passes thresholds |
| 2. Service | Capture API, upload, webhooks, viewer | End-to-end from upload to signed GLB |
| 3. Shadow | Event tap on real host uploads, results hidden | Success rate and quality compared with expectations; zero host impact |
| 4. Pilot | Gateway route enabled for a small group via flag | Stable SLOs, rollback tested |
| 5. General | Remaining tiers, masks, 3D Tiles, orthomosaic | Sign-off |

## 14. Risks, licensing and open questions

- **Licensing**: verify every dependency. For example, OpenMVS is AGPL-3.0 (running it as a separate service you control is one thing; redistributing or exposing it needs care) and some research models carry non-commercial terms. COLMAP and GLOMAP are permissively licensed. If the host project is commercial, get this checked before Phase 4.
- **Footage quality is the real ceiling**: motion blur, rolling shutter, low texture and moving objects cause most failures; the quality gate reduces but does not remove this.
- **Absolute accuracy without GCPs** is limited by GPS quality; offer an optional GCP or RTK input for survey-grade use.
- **Cost**: dense reconstruction is GPU-heavy; set per-tier budgets and track cost per capture from day one.
- **Open decisions**: which host events are available (storage events vs webhooks vs API), target scene size, required exports, expected daily volume, and where the viewer will be hosted.
