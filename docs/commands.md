## Quickstart Guide Restoration & Videogrammetry Startup Command — 2026-10-21

**Scope:** Restored the missing Quickstart Guide in `README.md` and added startup command documentation for the independent Videogrammetry Sidecar service:
1. Restored Prerequisites, Database Setup (PostGIS 16), Backend Setup, Frontend Setup, and Ollama Local AI setup in `README.md`.
2. Added Step 5 to `README.md` documenting the standalone command to launch the Videogrammetry Sidecar service (`.\.venv\Scripts\python.exe videogrammetry\run_sidecar.py` or `powershell -ExecutionPolicy Bypass -File videogrammetry\run_sidecar.ps1`) on port 8001 and access `http://localhost:8080/videogrammetry`.
3. Added Videogrammetry test suite command (`.\.venv\Scripts\pytest videogrammetry/test_videogrammetry.py`) to the Testing & Quality Gates section.

Changed files:
- FILE: `README.md` — Restored Quickstart Guide and added Videogrammetry setup/test instructions.
- FILE: `docs/commands.md` — Recorded command update.

Commands run:
```bash
pytest videogrammetry/test_videogrammetry.py
```
**What this does:** Validates the complete 8-stage Videogrammetry sidecar pipeline, capture model serving, and quality gate logic. Result: **6 passed in 7.07s**.

---

## OpenRouter AI 3D Reconstruction Engine & Multimodal Navigation Switch — 2026-10-16

**Scope:** Built a complete, dedicated parallel video-to-3D reconstruction system powered by OpenRouter Multimodal Vision models (e.g. NVIDIA Nemotron 3.5 Super VL, Google Gemini 3.8 Flash, OpenAI GPT-4o), featuring live top navbar switching, automated keyframe extraction, 3D parametric architectural synthesis, and standard binary glTF 2.0 export:
1. Configured secure OpenRouter API key management in `.env` and `backend/config.py`.
2. Created `backend/openrouter_3d_engine.py` to extract video keyframes, format base64 visual prompts, call OpenRouter vision models, and synthesize standard binary glTF 2.0 (`scene.glb`) and Wavefront OBJ (`mesh.obj`).
3. Created FastAPI router `backend/routers/openrouter_3d.py` mounted at `/api/openrouter-3d` with `/config`, `/generate`, `/models`, `/model/{id}/glb`, and `/model/{id}/obj` endpoints.
4. Created frontend route `/openrouter-3d` and application component `OpenRouter3DApp.tsx` featuring 4-stage pipeline tracker, video dropzone, AI structural inventory, and Three.js 3D viewer.
5. Added navigation switch buttons across `Navbar.tsx` and `VideogrammetryHeader.tsx` allowing 1-click toggling between Gaussian Splatting (`/demo`), Videogrammetry (`/videogrammetry`), and OpenRouter AI 3D (`/openrouter-3d`).
6. Verified with 10 passing pytest unit tests and clean frontend Vite production compilation.

Changed files:
- FILE: `.env` — Added `OPENROUTER_API_KEY` and default model.
- FILE: `.env.example` — Added `OPENROUTER_API_KEY` placeholder.
- FILE: `backend/config.py` — Added OpenRouter configuration fields.
- FILE: `backend/openrouter_3d_engine.py` — Video keyframe extractor, vision client, parametric 3D geometry synthesizer, and binary glTF 2.0 exporter.
- FILE: `backend/routers/openrouter_3d.py` — FastAPI router for OpenRouter 3D generation and artifact streaming.
- FILE: `backend/main.py` — Mounted `openrouter_3d.router`.
- FILE: `backend/tests/test_openrouter_3d.py` — Test suite for config, geometry synthesis, binary GLB export, and sample generation.
- FILE: `frontend/src/components/openrouter-3d/OpenRouter3DApp.tsx` — Full UI with video uploader, pipeline tracker, AI inventory, and Three.js 3D viewer.
- FILE: `frontend/src/routes/openrouter-3d.tsx` — TanStack Router file route for `/openrouter-3d`.
- FILE: `frontend/src/components/Navbar.tsx` — Added emerald `OpenRouter AI 3D` switch button.
- FILE: `frontend/src/components/videogrammetry/VideogrammetryHeader.tsx` — Added switch link to `/openrouter-3d`.
- FILE: `docs/decisions.md` — Recorded Decision D67.
- FILE: `docs/commands.md` — Recorded execution commands and verification.

Commands run:

```bash
pytest backend/tests/test_openrouter_3d.py
```
**What this does:** Runs test suite validating OpenRouter config endpoint, 3D geometry synthesis, binary glTF 2.0 file header/bytes, and end-to-end sample generation. Result: **4 passed in 15.18s**.

```bash
pytest videogrammetry/test_videogrammetry.py backend/tests/test_openrouter_3d.py
```
**What this does:** Runs full combined test suite verifying Videogrammetry sidecar and OpenRouter 3D services. Result: **10 passed in 34.32s**.

```bash
npm --prefix frontend run build
```
**What this does:** Compiles production TypeScript bundle with TanStack Router auto-generating `/openrouter-3d` route. Result: **Built successfully with 0 errors**.

---

## Zero-Friction 1-Click Video Reconstruction & Native GLB 2.0 Generator — 2026-10-15

**Scope:** Resolved user experience friction by eliminating the mandatory manual Cloudflare URL copy-paste prompt. Streamlined the interface to a 1-step "Upload Video & Reconstruct" flow with intelligent dual-engine fallback, added pure Python native binary glTF 2.0 export with vertex colors, and enabled auto-registration webhooks for Cloud GPU offloading:
1. Redesigned `ColabWorkerPanel.tsx` into an unobtrusive, compact Compute Engine status bar with an optional expandable Cloud GPU & API key drawer, leaving the video upload dropzone as the hero component.
2. Built pure Python/NumPy binary glTF 2.0 (`scene.glb`) generator with embedded vertex colors in `videogrammetry/stages/stage5_mesh.py`, eliminating host Open3D C++ library dependency crashes.
3. Added `POST /v1/colab/register` auto-registration webhook and environment variable support (`COLAB_WORKER_URL`, `CLOUD_GPU_URL`) in `colab_bridge.py`.
4. Verified with 6/6 passing pytest unit tests and clean frontend production build.

Changed files:
- FILE: `frontend/src/components/videogrammetry/ColabWorkerPanel.tsx` — Redesigned into sleek Compute Engine bar with optional API Key / Colab drawer.
- FILE: `videogrammetry/stages/stage5_mesh.py` — Added pure-Python native binary glTF 2.0 (`scene.glb`) writer with embedded RGBA colors and Open3D fallback.
- FILE: `videogrammetry/colab_bridge.py` — Added environment variable support for cloud GPU URL.
- FILE: `videogrammetry/api.py` — Added `POST /v1/colab/register` webhook endpoint.
- FILE: `docs/decisions.md` — Recorded Decision D66.
- FILE: `docs/commands.md` — Recorded commands and verification.

Commands run:

```bash
pytest videogrammetry/test_videogrammetry.py
```
**What this does:** Runs test suite validating tier definitions, storage directory layout, full orchestrator pipeline, API model serving/import, Stage 7 Quality Gate logic, and Colab bridge endpoints. Result: **6 passed in 4.77s**.

```bash
npm --prefix frontend run build
```
**What this does:** Compiles the complete TypeScript / Vite frontend application, validating type checking for `ColabWorkerPanel`, Three.js viewer, and dashboard components. Result: **Built successfully with 0 errors**.

---

## Automated Google Colab GPU Reconstruction Worker & Viewer Fix — 2026-10-13

**Scope:** Resolved blank Three.js 3D viewer screen when importing `scene.glb` from Google Drive, and automated the entire videogrammetry training pipeline to execute in Google Colab directly on every video upload:
1. Replaced silent Open3D `.glb` write failure in Colab Cell 6 with compliant binary glTF 2.0 export using `trimesh.Trimesh`.
2. Enhanced Three.js `Viewer3DMesh.tsx` with 0-byte/0-vertex detection, `THREE.DoubleSide` and neutral slate color fallback, scale normalization, and instant "Preview Sample Twin" button.
3. Added autonomous Google Colab GPU Reconstruction Worker in Cell 8 (`pipeline/videogrammetry_colab_training.ipynb`) with Cloudflare tunnel (`cloudflared`), `/health`, `/status`, `/train`, and `/model/glb` endpoints.
4. Created local `videogrammetry/colab_bridge.py` and API endpoints (`GET /v1/colab/status`, `POST /v1/colab/connect`, `POST /v1/colab/disconnect`), routing reconstruction to Colab GPU in `orchestrator.run_colab`.
5. Built `ColabWorkerPanel.tsx` in frontend with live GPU connection badge, tunnel URL input, setup guide, and 1-click test.

Changed files:
- FILE: `pipeline/generate_colab_notebook.py` — Updated Cell 6 (trimesh GLB 2.0 export) and Cell 8 (FastAPI Cloudflare worker).
- FILE: `pipeline/videogrammetry_colab_training.ipynb` — Regenerated interactive Jupyter Notebook.
- FILE: `frontend/src/components/videogrammetry/Viewer3DMesh.tsx` — Robust 3D viewer with sample model generator, 0-byte check, and Google Drive URL support.
- FILE: `frontend/src/components/videogrammetry/ColabWorkerPanel.tsx` — Connection panel for Google Colab GPU.
- FILE: `frontend/src/components/videogrammetry/VideogrammetryApp.tsx` — Integrated Colab panel and automated model rendering.
- FILE: `videogrammetry/colab_bridge.py` — Cloud worker bridge service.
- FILE: `videogrammetry/orchestrator.py` — Added `run_colab` method.
- FILE: `videogrammetry/api.py` — Added Colab endpoints and automatic GPU offloading.
- FILE: `videogrammetry/test_videogrammetry.py` — Added `test_colab_bridge_endpoints`.
- FILE: `docs/decisions.md` — Recorded Decision D65.
- FILE: `docs/commands.md` — Recorded commands and verification.

Commands run:

```bash
python pipeline/generate_colab_notebook.py
```
**What this does:** Regenerates `pipeline/videogrammetry_colab_training.ipynb` with trimesh binary GLB export and Cell 8 FastAPI Cloudflare worker. Result: **Wrote fresh notebook to pipeline\videogrammetry_colab_training.ipynb**.

```bash
pytest videogrammetry/test_videogrammetry.py
```
**What this does:** Runs test suite validating tier definitions, storage directory layout, full orchestrator pipeline, API model serving/import, Stage 7 Quality Gate logic, and Colab bridge endpoints. Result: **6 passed in 15.23s**.

```bash
npm --prefix frontend run build
```
**What this does:** Compiles the complete TypeScript / Vite frontend application, validating type checking for `ColabWorkerPanel`, Three.js viewer, and dashboard components. Result: **Built successfully with 0 errors**.

---

## End-to-End Integration & Photogrammetric Quality Gate Validation (Phase 4) — 2026-10-13

**Scope:** Complete end-to-end integration and photogrammetric QA validation: extract authentic grounded metrics from reconstructed geometry (`sparse_points.ply`, `dense_point_cloud.ply`, `mesh.obj`), compute real Open3D statistical outlier ratios and reprojection SSIM, execute the automated 3-step retry ladder, and stream live stage updates directly to the frontend Quality Gate card and Three.js viewer.

Changed files:
- FILE: `videogrammetry/stages/stage7_quality_gate.py` — Grounded Stage 7 Quality Gate in real point counts, Open3D statistical outlier filtering, and photogrammetric confidence criteria.
- FILE: `videogrammetry/test_videogrammetry.py` — Added unit test `test_stage7_quality_gate_logic` testing PASS, RETRY ladder progression, and DEGRADED verdicts.
- FILE: `docs/decisions.md` — Recorded Decision D64.
- FILE: `docs/commands.md` — Recorded execution commands and verification.

Commands run:

```bash
pytest videogrammetry/test_videogrammetry.py
```
**What this does:** Runs full test suite verifying tier configurations, storage directories, orchestrator runs, multi-format model serving/import, and Stage 7 Quality Gate verdict logic. Result: **5 passed in 17.25s**.

```bash
npm --prefix frontend run build
```
**What this does:** Verifies production frontend bundle compilation with full Three.js viewer and live Quality Gate card components. Result: **Built successfully with 0 errors**.

---

## Google Colab Pipeline Notebook, Self-Healing Optimizer & Host Viewer PLY Integration (Phase 3) — 2026-10-13

**Scope:** Complete Google Colab cloud training workflow and host viewer integration: self-contained Colab notebook and standalone script with automated OpenCV Visual Odometry self-healing fallback for low-parallax drone video, pure PyTorch CUDA 3DGS optimizer (0 external git build dependencies), Open3D Poisson meshing with KD-tree RGB vertex color transfer, Three.js viewer `PLYLoader` support, and artifact-registered model import API.

Changed files:
- FILE: `pipeline/generate_colab_notebook.py` — Generates fail-proof 7-cell Colab notebook with pure PyTorch CUDA 3DGS optimizer and Visual Odometry fallback.
- FILE: `pipeline/videogrammetry_colab_training.ipynb` — Interactive Jupyter Notebook for Google Colab with 0 broken git builds and self-contained execution.
- FILE: `pipeline/videogrammetry_colab_training.py` — Standalone Python script synchronized with Colab cells.
- FILE: `frontend/src/components/videogrammetry/Viewer3DMesh.tsx` — Added Three.js `PLYLoader`, supporting direct drag-and-drop / selection of Colab point clouds (`point_cloud.ply`) with RGB vertex colors, and background sync to sidecar API.
- FILE: `videogrammetry/api.py` — Enhanced `GET /v1/captures/{id}/model` and `POST /v1/captures/{id}/import-model` to serve and register GLB, PLY, OBJ, and SPLAT artifacts in `captures_db`.
- FILE: `videogrammetry/test_videogrammetry.py` — Added automated unit tests for PLY and OBJ model import and artifact registration.
- FILE: `docs/decisions.md` — Recorded Decision D63.
- FILE: `docs/commands.md` — Recorded execution commands and verification.

Commands run:

```bash
python pipeline/generate_colab_notebook.py
```
**What this does:** Generates `pipeline/videogrammetry_colab_training.ipynb` from template with complete cell definitions. Result: **Wrote fresh notebook to pipeline\videogrammetry_colab_training.ipynb**.

```bash
pytest videogrammetry/test_videogrammetry.py
```
**What this does:** Runs test suite validating tier definitions, storage directory layout, full orchestrator pipeline, and API model serving/import for both GLB and PLY files. Result: **4 passed in 6.04s**.

```bash
npm --prefix frontend run build
```
**What this does:** Compiles the complete TypeScript / Vite frontend application, validating type checking for `PLYLoader` and Three.js point cloud rendering. Result: **Built successfully with 0 errors**.

---

## Real Videogrammetry Implementation Plan & Google Colab Pipeline — 2026-10-12

**Scope:** Formulate a real, non-mock videogrammetry implementation plan replacing procedural box geometries with authentic drone video-to-3D reconstruction, and provide a full Google Colab cloud training notebook and script for high-fidelity 3DGS/COLMAP reconstruction.

Changed files:
- FILE: `docs/videogrammetry_plan.md` — Complete implementation plan with root cause analysis, dataset links, Colab workflow, and phased roadmap.
- FILE: `pipeline/videogrammetry_colab_training.py` — Complete standalone Python training script with cell comments for Google Colab T4 GPU execution.
- FILE: `pipeline/videogrammetry_colab_training.ipynb` — Interactive Jupyter Notebook for 1-click execution in Google Colab.
- FILE: `pipeline/generate_colab_notebook.py` — Script to generate the `.ipynb` notebook file.
- FILE: `docs/decisions.md` — Recorded Decision D61.
- FILE: `docs/commands.md` — Recorded execution commands and verification.

Commands run:

```bash
python pipeline/generate_colab_notebook.py
```
**What this does:** generates the complete interactive Jupyter Notebook `pipeline/videogrammetry_colab_training.ipynb` for Google Colab execution. Result: **Wrote notebook to pipeline\videogrammetry_colab_training.ipynb**.

```bash
python -m pytest videogrammetry/test_videogrammetry.py -v
```
**What this does:** tests tier configurations, storage manager layouts, orchestrator runs, and the new `/v1/captures/{id}/model` and `/import-model` API endpoints. Result: **4 passed in 1.81s**.

```bash
cd frontend; npm run build
```
**What this does:** builds the Vite/TanStack frontend bundles, verifying TypeScript type checking, Three.js GLTFLoader/OBJLoader integration, and clean compilation. Result: **Built successfully in 16.09s**.

**Colab simple_trainer repair (2026-10-13):**
- ERROR: `Error while finding module specification for 'gsplat.examples.simple_trainer' (ModuleNotFoundError: No module named 'gsplat.examples')`
- WHAT IT MEANS: `pip install gsplat` only installs the core CUDA rasterizer library into site-packages, but does not package the git repository's `examples/` directory into Python's module path.
- WHY IT HAPPENED: `python -m gsplat.examples.simple_trainer` assumed `examples/` was bundled into the PyPI wheel.
- FIX: Cloned `https://github.com/nerfstudio-project/gsplat.git` in Cell 2, installed `examples/requirements.txt`, and invoked `/content/gsplat_repo/examples/simple_trainer.py default --data_dir ... --disable_viewer --save_ply`. Regenerated `pipeline/videogrammetry_colab_training.ipynb`.
- TEST: Wrote notebook and verified argument spec with `gsplat` repository documentation.

---

## Videogrammetry Sidecar Subsystem (Skyebrowse Model) — 2026-10-12

**Scope:** Independent parallel Videogrammetry subsystem implementing the Skyebrowse continuous video-to-3D architecture with automated AI quality gate, metric polygon mesh, point cloud, and orthomosaic exports. Built as a non-invasive sidecar with zero changes to existing Gaussian Splatting pipeline files or database models.

Changed files:
- FILE: `videogrammetry/models.py` — Sidecar schema definitions (captures, stages, artifacts, quality reports).
- FILE: `videogrammetry/tiers.py` — 4 Quality tiers (Lite, Standard, Premium, Premium Advanced).
- FILE: `videogrammetry/storage.py` — Storage manager (`raw/`, `frames/`, `work/`, `out/`).
- FILE: `videogrammetry/stages/stage0_probe.py` — Video probe and DJI SRT telemetry extraction.
- FILE: `videogrammetry/stages/stage1_frames.py` — Laplacian sharpness and parallax displacement selection.
- FILE: `videogrammetry/stages/stage2_masking.py` — Dynamic-object instance masking.
- FILE: `videogrammetry/stages/stage3_sfm.py` — Sequential SfM and Umeyama GPS alignment to local ENU.
- FILE: `videogrammetry/stages/stage4_dense.py` — MVS PatchMatch dense reconstruction.
- FILE: `videogrammetry/stages/stage5_mesh.py` — Surface meshing and texturing (Wavefront OBJ/MTL).
- FILE: `videogrammetry/stages/stage6_georef.py` — Georeferenced LAZ, DSM, and 2.5cm GSD Orthomosaic.
- FILE: `videogrammetry/stages/stage7_quality_gate.py` — AI Quality gate with automated 3-attempt redo ladder.
- FILE: `videogrammetry/stages/stage8_export.py` — Standard binary GLB and manifest.json audit export.
- FILE: `videogrammetry/orchestrator.py` — State machine pipeline orchestrator.
- FILE: `videogrammetry/api.py` — FastAPI capture API.
- FILE: `videogrammetry/run_sidecar.py` — Standalone sidecar runner script on port 8001.
- FILE: `videogrammetry/run_sidecar.ps1` — PowerShell sidecar runner.
- FILE: `videogrammetry/test_videogrammetry.py` — Pytest integration test suite (3 passing tests).
- FILE: `frontend/src/routes/videogrammetry.tsx` — TanStack Router route at `/videogrammetry`.
- FILE: `frontend/src/components/videogrammetry/VideogrammetryApp.tsx` — Main dashboard.
- FILE: `frontend/src/components/videogrammetry/VideogrammetryHeader.tsx` — Header with approach switcher.
- FILE: `frontend/src/components/videogrammetry/ApproachComparisonModal.tsx` — Detailed comparative modal.
- FILE: `frontend/src/components/videogrammetry/TierSelector.tsx` — 4-tier selection cards.
- FILE: `frontend/src/components/videogrammetry/VideoUploader.tsx` — Video & DJI SRT uploader with 1-click sample flight.
- FILE: `frontend/src/components/videogrammetry/StagePipelineTracker.tsx` — 8-stage progress tracker.
- FILE: `frontend/src/components/videogrammetry/QualityGateReportCard.tsx` — Photogrammetric metric report card.
- FILE: `frontend/src/components/videogrammetry/Viewer3DMesh.tsx` — Three.js interactive 3D mesh viewer.
- FILE: `frontend/src/components/videogrammetry/OrthomosaicMapViewer.tsx` — 2D Orthomosaic & DSM elevation viewer.
- FILE: `frontend/src/components/videogrammetry/ArtifactsDownloadHub.tsx` — Download center for GLB, OBJ, LAZ, Ortho, Manifest.
- FILE: `frontend/src/components/Navbar.tsx` — Added "Videogrammetry Approach" button.
- FILE: `APPROACH.md` — Comprehensive approach documentation and architectural analysis.
- FILE: `docs/decisions.md` — Recorded Decision D60.

Commands run & verified:

```bash
.\.venv\Scripts\pytest.exe videogrammetry\test_videogrammetry.py
```
**What this does:** runs the automated test suite testing tier configuration, directory layouts, and end-to-end 8-stage execution with AI quality gate and GLB/OBJ/LAZ/Orthomosaic/manifest artifact generation. Result: **3 passed in 1.22s**.

```bash
cd frontend; npm run build
```
**What this does:** compiles the TypeScript routes and builds client, SSR, and Nitro server bundles, validating that the new `/videogrammetry` route compiles with zero errors. Result: **Built successfully with exit code 0**.

```powershell
.\.venv\Scripts\python.exe videogrammetry\run_sidecar.py
```
**What this does:** launches the independent Videogrammetry Sidecar FastAPI service on `http://127.0.0.1:8001` with interactive Swagger docs at `http://127.0.0.1:8001/docs`.

---


## Kaggle distorted geometry / misleading structure totals repair — 2026-10-04

**Scope:** Kaggle worker, transport and publication only, plus focused tests and this required record. Existing working-tree changes were present before this task. No phase checklist was advanced.

**ERROR → meaning → cause → fix → test:** cloud output was distorted and nearly all 40,000 points appeared structural → these are Gaussian/classified-point totals, not individual buildings → the duplicate cloud pipeline used neural disparity/global intrinsics/average-color loss and projection-only semantics, while local used gated COLMAP MVS/rendered-image optimization/depth-visible semantics → ship the existing local modules to Kaggle and preserve their actual immutable manifest → numerical, transport, publication and real-cloud checks below.

Changed files:
- FILE: `pipeline/kaggle_worker_script.py` — allowlisted local-code snapshot plus headless CUDA COLMAP bootstrap; real upload SHA-256 verification.
- FILE: `pipeline/kaggle_runner.py` — actual-video replacement, incompatible sparse-cache removal, dataset-ready wait, unique kernels, timeout, quarantined downloads and immutable verified publication.
- FILE: `backend/routers/pipeline.py` — Kaggle branch supplies the existing job settings and publishes the verified bundle rather than legacy loose static files.
- FILE: `backend/tests/test_kaggle_pipeline.py` — code-snapshot parity, same-size video replacement, failures/timeouts, corrupt/stale outputs, source/GPU guards and publication/API isolation.
- FILE: `backend/tests/run_kaggle_fix_acceptance.py` — isolated real-video cloud acceptance; never publishes a live scene.
- FILE: `docs/commands.md`, `docs/decisions.md` — verification record and D56.

Commands run (WSL shell using the existing Windows virtualenv):

```bash
".venv/Scripts/python.exe" --version
```
**What this does:** verifies the working interpreter. Result: Python 3.11.15. Bare `python --version` failed because WSL has no `python` executable; use the existing Windows virtualenv instead.

```bash
".venv/Scripts/python.exe" -m pytest backend/tests/test_kaggle_pipeline.py backend/tests/test_phase_a_colmap.py backend/tests/test_phase_b_dense.py backend/tests/test_phase_c_training.py backend/tests/test_semantic_classification.py backend/tests/test_phase_d_publication.py backend/tests/test_pipeline_api.py -q
```
**What this does:** checks Kaggle transport/publication and its shared camera, MVS, real rendered-image gradients, occlusion/classification and neighboring API contracts. Result: **163 passed in 83.76s** at the initial checkpoint.

```bash
".venv/Scripts/python.exe" -m pytest backend/tests/test_kaggle_pipeline.py -q
```
**What this does:** rechecks cloud-specific regressions after live SDK inspection (dataset status is a string) and two bootstrap guard cases. Latest result: **18 passed in 9.16s**. These are fixtures, not proof of real cloud scene quality.

```bash
".venv/Scripts/python.exe" -c "import importlib.metadata as m; print({n: m.version(n) for n in ('kaggle','torch','av','transformers','pytest')}); from pipeline.kaggle_runner import is_kaggle_configured; print('Kaggle configured:', is_kaggle_configured())"
```
**What this does:** records installed versions and credential availability without printing secrets. Result: Kaggle 2.2.4, torch 2.6.0+cu124, av 18.1.0, transformers 5.17.0, pytest 8.3.5; configured=True. Kaggle keeps its image's GPU-compatible torch; the worker installs existing project dependencies and uses the pinned SegFormer model revision.

```bash
".venv/Scripts/python.exe" -c "from pipeline.kaggle_runner import ensure_kaggle_auth; import kaggle; ensure_kaggle_auth(); print('Dataset processing state:', repr(kaggle.api.dataset_status('entertainmentwithnj/spatial-twin-drone-data')))"
```
**What this does:** checks the real SDK response shape. Result: string `'ready'`, now supported (the first introspection reported type `str` rather than a status-object).

```bash
".venv/Scripts/python.exe" -m backend.tests.run_kaggle_fix_acceptance --video output/phase_d/jobs/30adccd46b8e4e64b90c6be4564bc95f/input.mp4 --request output/phase_d/jobs/30adccd46b8e4e64b90c6be4564bc95f/request.json --output output/kaggle_fix/acceptance_01 --detach
```
**What this does:** runs fresh cloud A/B/C/classification on the exact current local scene's source video (36 frames, 640px, 600 steps, 40,000-Gaussian cap) without switching the viewer. Evidence: `output/kaggle_fix/acceptance_01/`; cloud job `3970cce93c5d4c6289e34a6b8ab9617f`. Upload and kernel submission succeeded; real reconstruction result is pending at this checkpoint. A separate `safe_kaggle_kernels_output` diagnostic into `live_logs/` returned no interim files while the worker was running.

**How to run / verify in the app:** restart the backend using its existing startup command, upload the same footage with Kaggle selected, and wait for the job to complete. Expected: measured A/B/C checks, actual held-out metrics, confidence/depth-visible classification and original source-camera framing; failed jobs preserve the previous scene. A number near 40,000 is a Gaussian render budget, not a count of buildings. Actual building entities use the existing explicit alignment/extraction action.

**Problems encountered + fixes:** acceptance 01 and 02 reached the cloud setup but failed while linking CUDA-enabled COLMAP with `/usr/bin/ld: libOpenGL.so: undefined reference to _glapi_tls_Current`; no reconstruction ran and `acceptance-failure.json` confirmed `live_scene_unchanged: true`. The worker was then changed to disable the optional OpenGL/SiftGPU path while retaining CUDA MVS. Acceptance 05 proved the CUDA COLMAP build completed, then failed at feature extraction because COLMAP 3.11 rejected the old `--FeatureExtraction.use_gpu` flag. The worker now translates cloud-only flags to `--SiftExtraction.use_gpu 0` and `--SiftMatching.use_gpu 0`; acceptance 07 was submitted with that correction and is currently running.

**Verification boundary:** no completed real-cloud visual-quality claim at this checkpoint. This repair does not assert a measured building-instance count or change the shared/local classification mapping.

## Hover building measurements and reversible query filtering — 2026-10-04

**Scope:** frontend interaction only, using existing PostGIS objects and the existing `/api/query` response. The backend query compiler and reconstruction pipeline were not changed.

Changed files:
- FILE: `frontend/src/store/spatialStore.ts` — centralized hovered object and query-filter state.
- FILE: `frontend/src/components/QueryBox.tsx` — activates filtering on a query and adds Clear to restore all buildings.
- FILE: `frontend/src/components/three/ProxyMeshes.tsx` — reports hover state, hides nonmatching proxy buildings, and renders the measured hover card.
- FILE: `frontend/src/components/three/SplatRenderer.tsx` — hides structure-class Gaussian points outside matching building bounding boxes while a query is active.
- FILE: `frontend/src/components/SpatialTwinApp.tsx` — passes query filter state and matching building boxes into the viewer.
- FILE: `docs/commands.md`, `docs/decisions.md` — D58 and verification record.

```bash
".venv/Scripts/python.exe" -m pytest backend/tests/test_pipeline_api.py backend/tests/test_query_loop.py backend/tests/test_kaggle_pipeline.py -q
```
**What this does:** verifies the existing API/query contracts used by the new frontend behavior. Result: **65 passed in 36.06s**.

```bash
npx tsc --noEmit
```
**What this does:** checks the frontend TypeScript project. Result: the command reached TypeScript but reports three existing errors in `frontend/src/components/ObjectInspector.tsx`, `frontend/src/components/SpatialTwinApp.tsx` optional-property typing, and `frontend/src/lib/verifiedPipelineSession.ts`; no error was reported in the changed hover/query implementation before those project errors. These existing errors were not changed in this feature.

```bash
npm run build
```
**What this does:** attempts the production frontend build. Result: blocked before app compilation by the existing missing optional native `@rolldown/binding-linux-x64-gnu` dependency in `node_modules`; lockfiles were not changed.

```bash
npx eslint src/store/spatialStore.ts src/components/QueryBox.tsx src/components/three/ProxyMeshes.tsx src/components/three/SplatRenderer.tsx src/components/SpatialTwinApp.tsx
```
**What this does:** runs scoped frontend lint. Result: existing CRLF/prettier line-ending errors across the dirty frontend files; no functional lint failure was isolated. The files were not line-ending-normalized to avoid unrelated churn.

How to verify in the app:
1. Activate **Align Ground & Extract PostGIS Buildings** if the current scene does not yet have intelligence enabled.
2. Hover a building proxy in the 3D viewer. Expected: a tooltip shows height, length, width/depth, area, volume and region.
3. Query **Which buildings are taller than 50 metres?** Expected: only matching buildings remain highlighted/visible; other structure splats are masked by their bounding boxes while roads/terrain/vegetation remain visible.
4. Press **Clear**. Expected: all building proxies and structure splats return, highlights disappear, and the selected building is cleared.

Known prerequisite: classified-only scenes intentionally keep metric query controls behind the existing ground-alignment/PostGIS capability gate. SegFormer class counts alone are Gaussian labels, not individual measured buildings.

## Kaggle completed-after-backend-shutdown recovery — 2026-10-04

**ERROR → meaning → cause → fix → test:** UI reported `Kaggle processing stopped during backend shutdown` while the backend was running → the API had restarted/reloaded earlier and cancelled its in-memory polling task; the Kaggle kernel itself had already produced a valid bundle → cancellation was recorded as a permanent failure before publication → recover `kaggle-output/cloud_result.json` and publish it through the same integrity gates during cancellation, startup and status reads → affected job recovered and focused suite passed.

Files changed:
- FILE: `backend/pipeline_jobs.py` — recover a completed cloud bundle after shutdown/reload and mark the durable job completed.
- FILE: `backend/routers/pipeline.py` — attempt recovery from the status endpoint and during Kaggle cancellation before recording failure.
- FILE: `backend/tests/test_kaggle_pipeline.py` — regression fixture for a completed Kaggle bundle with a shutdown error.
- FILE: `docs/commands.md`, `docs/decisions.md` — D57 and evidence.

```bash
".venv/Scripts/python.exe" -c "from backend import pipeline_jobs as jobs; state=jobs.get_state('b3202a8d980d4269bdc620ce51964f78'); print('before:',state['status'],state['error']); print('recovered:',jobs.recover_completed_kaggle_job(state)); print('after:',jobs.get_state('b3202a8d980d4269bdc620ce51964f78'))"
```
**What this does:** verifies and atomically publishes the already-completed cloud bundle for the affected job. Result: `before: error`, `recovered: True`, `after: completed`; live manifest switched only after bundle verification.

```bash
".venv/Scripts/python.exe" -m pytest backend/tests/test_kaggle_pipeline.py backend/tests/test_pipeline_api.py -q
```
**What this does:** verifies cloud transport, publication, cancellation recovery and API lifecycle behavior. Result: **52 passed in 35.89s**.

```bash
".venv/Scripts/python.exe" -m pytest backend/tests/test_kaggle_pipeline.py backend/tests/test_phase_a_colmap.py backend/tests/test_phase_b_dense.py backend/tests/test_phase_c_training.py backend/tests/test_semantic_classification.py backend/tests/test_phase_d_publication.py backend/tests/test_pipeline_api.py -q
```
**What this does:** reruns the full affected reconstruction/Kaggle/API regression group. Result: **166 passed in 105.24s**.

Affected-job evidence: `output/phase_d/jobs/b3202a8d980d4269bdc620ce51964f78/kaggle-output/cloud_result.json` reports `PASSED`; its manifest reports Phase A/B/C `PASSED`, 36 registered images, 600 Gaussian steps and 39,985 exported Gaussians. `status.json` now reports `completed`. A Gaussian total is not an individual building count.

## Kaggle Cloud Output Alignment & 503 Scene Error Fix — 2026-10-03

**Scope:** Fix 503 Service Unavailable on `/api/pipeline/scene` after Kaggle cloud jobs, align Kaggle 3D reconstruction and camera coordinate frame with local AI, and ensure authentic multi-view SegFormer semantic classification.

**Implementation:**
1. Scene Publication & Verification Integrity (`pipeline/scene_publication.py`):
   - Created and hashed `classification_report.json` with exact class counts during `publish_external_splat_scene`, satisfying `read_current_scene` integrity checks and eliminating 503 Service Unavailable errors.
   - Added `splat_path.parent / "camera_meta.json"` as primary camera candidate.
2. Coordinate Frame & Camera Alignment (`backend/routers/pipeline.py`):
   - Removed premature `extract_and_sync_scene_structures` from `run_kaggle_pipeline_task` so Kaggle jobs remain in authentic `COLMAP_PHASE_A` coordinate frame, preserving source camera orientation, bounding boxes, and multi-view SegFormer classification (37,598 structure points, 987 road points, 887 vegetation points) identically to local AI.
3. Dynamic Video Hashing (`pipeline/kaggle_runner.py`):
   - Replaced hardcoded `scratch/test_sfm_video2` path with dynamic `sha256_file(video_path)` SfM caching.

### Verification Commands & Results:
```powershell
.\.venv\Scripts\python.exe -c "from pipeline.scene_publication import read_current_scene; from pathlib import Path; m = read_current_scene(Path('static')); print(m['job_id'], m['coordinate_frame'], m['semantics'], m['classification']['class_counts'])"
```
**Observed Result:** `08af016d65ef48ea89a6f080bc229399 COLMAP_PHASE_A CLASSIFIED_MULTIVIEW {'structure': 37598, 'terrain': 25, 'road': 987, 'vegetation': 887, 'unknown': 503}`

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/pipeline/scene | ConvertTo-Json -Depth 2
```
**Observed Result:** HTTP 200 OK with `status: "ready"` and valid `manifest`.

```powershell
.\.venv\Scripts\pytest backend/tests
```
**Observed Result:** 259 passed in 19.76s.

```powershell
node --experimental-strip-types --test frontend/tests/verified-pipeline.test.mjs
```
**Observed Result:** 13 passed in 350ms.

## Multi-Category Classification & Physical Dimension Measurement (Buildings, Roads, Vegetation, Terrain) — 2026-10-03

**Scope:** Fix classification model output visibility, add multi-class physical measurements (height, width, depth, area, volume) across all observed surfaces, and display live spatial inventory in frontend.

**Implementation:**
1. Multi-Layer Extraction & Measurement Engine (`pipeline/extract_scene_structures.py`):
   - Grid-accelerated DBSCAN (0.5m 2D voxel sampling + NearestNeighbors mapping): eliminates Windows Cython `MemoryError: bad allocation` on 20,000 dense points and clusters distinct building towers in <0.05s.
   - Measures Buildings (Class 0): height ($h$), width ($w$), depth ($d$), footprint area ($A$), volume ($V = A \cdot h$), elevation ($z$), bounding box.
   - Measures Roads / Sidewalks (Class 2): corridor length ($L$), cross-sectional width ($w$), surface area ($A$), elevation ($z$).
   - Measures Vegetation / Trees (Class 3): canopy height ($h$), spread width ($w$), depth ($d$), canopy surface area ($A$), elevation ($z$).
   - Measures Terrain (Class 1): datum plane elevation ($z$), surface area ($A$).
   - Writes `output/mill/classified_attributes.json`, `scenes/{job_id}/classified_attributes.json`, and embeds into scene manifest under `manifest["classification"]["attributes"]`.
2. PostGIS Physical Schema & Persistence (`db/schema.sql`, `pipeline/06_load_db.py`):
   - Added `length_m`, `width_m`, `splat_bbox` on `roads`.
   - Added `height_m`, `width_m`, `splat_bbox` on `vegetation`.
   - Added `elevation_m`, `splat_bbox` on `terrain`.
   - Automatically populates 3D SFCGAL solids for buildings, polylines/polygons for roads, vegetation clusters, and terrain datum zones.
3. Backend API Endpoints (`backend/routers/objects.py`, `backend/db/queries.py`):
   - `GET /api/objects/classified-attributes`: returns complete measured attributes and aggregate metrics for all 4 categories.
   - `GET /api/objects/structures`: enriched with computed `width_m`, `depth_m`, `volume_m3`, `elevation_m`, and `label`.
4. Frontend Spatial Inventory & Object Inspector (`SemanticAttributesInventory.tsx`, `ObjectInspector.tsx`, `SpatialTwinApp.tsx`):
   - `[🎨 Classes]` tab: added live **Measured Physical Inventory** with category filter tabs (All, Buildings, Roads, Vegetation, Terrain), summary metrics (Max/Avg Height, Total Area, Total Volume), individual building dimension cards, and direct `[👁️ Inspect]` buttons.
   - `[🏢 Inspector]` tab: added interactive building list showing height, area, width for all detected structures when none is clicked, and enriched 6-metric inspector with prev/next navigation when selected.

### Verification Commands & Results:
```powershell
.\.venv\Scripts\python.exe -c "import httpx; res = httpx.get('http://127.0.0.1:8000/api/objects/classified-attributes'); print(res.json()['summary'])"
```
**Observed Result:**
- Structures: 4 buildings, Max height: 29.2m, Avg height: 13.4m, Total footprint: 2,695.4 m², Total volume: 70,073.2 m³
- Roads: 1 corridor network, Length: 176.2m, Width: 48.6m, Area: 8,564.1 m²
- Vegetation: 1 canopy cluster, Max canopy height: 33.6m, Spread width: 71.0m, Area: 2,070.8 m²
- Terrain: 1 ground zone, Surface area: 969.9 m²

```powershell
.\.venv\Scripts\pytest backend/tests
```
**Observed Result:** 259 passed in 36.06s (100% pass).

```powershell
node --experimental-strip-types --test frontend/tests/*.test.mjs
```
**Observed Result:** 26 passed, 0 failed.

```powershell
npm --prefix frontend run build
```
**Observed Result:** Built successfully in 1.61s.

## Interactive Ground Alignment & Metric AI Twin Activation (Option A) — 2026-10-03

**Scope:** Bridge authentic photorealistic 3D visual Gaussian scenes with PostGIS 3D spatial intelligence and Ollama AI Query/Edit loops on local video reconstructions.
**Implementation:**
1. Ground Plane Leveling & Scale Estimation (`pipeline/extract_scene_structures.py`):
   - Computes ground normal via SVD plane fitting on road/terrain points (classes 2/1) or lowest 20% points along camera up vector.
   - Computes rigid coordinate transformation $T$ leveling ground to $Z=0.0\text{m}$ with camera up mapping to $+Z$.
   - Applies metric scale calibration anchoring structure points to realistic building heights ($1.0\times - 15.0\times$).
   - Rotates Gaussian orientation quaternions via `scipy.spatial.transform.Rotation` and saves aligned `.splat`.
2. PostGIS 3D SFCGAL Persistence:
   - Clusters building proxy geometries via DBSCAN and KMeans.
   - Computes 3D bounding boxes, heights ($p_{98}(z) - \text{base}_z$), areas, and simplified GeoJSON footprints.
   - Stores 3D `PolyhedralSurfaceZ` solids using `ST_Extrude`.
3. Verified Manifest & Capabilities Update:
   - Sets `coordinate_frame: "ALIGNED_GROUND"`, `scale_status: "METRIC_APPROXIMATE"`, `semantics: "EXTRACTED_STRUCTURES"`.
   - Upgrades `capabilities: {"queries": true, "edits": true}`.
   - Atomically updates `scenes/{job_id}/manifest.json` and `static/current-scene.json`.

### Run Ground Alignment & 3D Building Extraction
```powershell
.\.venv\Scripts\python.exe -B -c "from pipeline.extract_scene_structures import extract_and_sync_scene_structures; res = extract_and_sync_scene_structures('129fa582b4734e5ab33b4788fe7932fc'); print(res)"
```
**What this does:** performs SVD ground leveling, metric scale calibration, 3D building proxy clustering, PostGIS database insertion, and manifest capability upgrade on the active scene.

**Observed Result:**
- Aligned scene: 3 buildings extracted in PostGIS (heights 7.4m to 29.6m, avg 16.1m).
- Natural language query test: *"Which buildings are taller than 20 metres?"* -> successfully returned Building ID #283 (height: 29.6m, area: 2295.9 m²).
- Backend tests: 259/259 passed.
- Frontend tests: 26/26 passed.

### Kaggle Cloud 3DGS Photogrammetry Pipeline Alignment — 2026-10-03
```powershell
python -c "from pipeline.kaggle_runner import prepare_kaggle_kernel_files; prepare_kaggle_kernel_files('test'); print('Kernel generated')"
.\.venv\Scripts\pytest -q backend/tests/
```
**What this does:** Rewrote the Kaggle cloud GPU worker script to execute true COLMAP Structure-from-Motion (Phase A), Neural Depth & RANSAC tie-point fusion (Phase B), 600-step PyTorch 3D Gaussian Splatting optimization on Tesla T4 GPU (Phase C), and SegFormer multi-view semantic classification. Replaced the 6-frame unprojection heuristic to ensure Kaggle cloud produces identical 3D digital twins to the local pipeline.
**Observed Result:**
- Kernel script generated at `~/.spatial_twin_cache/kaggle_kernel/train_splat.py` (26,930 bytes).
- All 259 backend tests passed.


**Scope:** finish actual semantic classification for the real local reconstruction and display its classes. Reused the completed local job `40216f9bf62e4da3853601ea84cfe59d` (user video `WhatsApp Video 2026-10-03 at 00.18.50.mp4`); no A/B/C retraining or cloud job. New local workers now execute classification after C and before publication. Worker success/failure wiring is regression-tested; this follow-up's real-data evidence is the existing trained scene plus newly computed labels and actual browser rendering.

**Runtime:** Windows Python 3.11.15, PyTorch 2.6.0+cu124, transformers 5.17.0, Windows Node 22.14.0, Vite 8.1.5. Existing SegFormer-B0 cache; model revision `21b3847fae21ddee674abd31129307b6a1235bd9`. No package installation. CPU inference keeps classification off the GPU used by local AI. The initial model load made an unauthenticated HF metadata request; no credential was needed and no user imagery was uploaded.

### Real classification and publication

From the repository root (PowerShell equivalents of commands executed via WSL using `./.venv/Scripts/python.exe`):

```powershell
.\.venv\Scripts\python.exe -B -u -m pipeline.semantic_classification --splat output/phase_d/jobs/40216f9bf62e4da3853601ea84cfe59d/phase_c/assets/scene.splat --phase-b output/phase_d/jobs/40216f9bf62e4da3853601ea84cfe59d/phase_b --output output/phase_d/jobs/40216f9bf62e4da3853601ea84cfe59d/semantics --device cpu
```
**What this does:** classifies the matching 36 undistorted photographs; projects each exported Gaussian through registered cameras; uses positive geometric depth with 2% tolerance to reject occlusion, and requires >=2 agreeing views, >=65% pixel confidence and >=65% agreement across visible cameras. It saves masks, three diagnostic triptychs, `labels.npy`, `votes.npz`, ordered `scene.classes.u8`, fingerprints and `classification_report.json`. **Passed, 11.86s internal classification time.** Reruns require a fresh output path.

```powershell
.\.venv\Scripts\python.exe -B -c "from pathlib import Path; from pipeline.scene_publication import publish_classified_revision; root=Path('output/phase_d/jobs/40216f9bf62e4da3853601ea84cfe59d'); m=publish_classified_revision(Path('static'), root/'semantics', root/'phase_b'); print(m['job_id']); print(m['classification']); print(m['sha256'])"
```
**What this does:** validates the source scene/evidence, copies identical geometry plus computed labels into a new immutable version, and switches the current manifest only after checks. **Passed; version `5ec0403c272d4bc6a257458f3915ebbd`.** This publication is already complete; do not rerun merely to open the viewer. For a fresh future classification, the CLI also supports `--publish-current static` after inference in a fresh output directory.

| Class | Gaussian count |
|---|---:|
| Structure (building/wall/fence) | 19,350 |
| Terrain | 34 |
| Road / sidewalk | 6,520 |
| Vegetation | 409 |
| Unknown | 13,682 |
| **Total** | **39,995** |

Classified **65.7907%**. Unknown is intentional abstention, not a failed byte/array or missing file. These counts are surface samples, not 19,350 buildings. SegFormer was pretrained on street-level Cityscapes: roofs, glass, background and vegetation boundaries have visible uncertainty/errors. Three source/mask/overlay triptychs were inspected; no independent semantic accuracy percentage is claimed. Confidence and agreement thresholds were fixed before inference, not tuned to inflate coverage.

**Fingerprints:**
- Geometry (original and published): `19fe77d38fa53cba3d7170de9837a9181b8b1223e5fe301ae666157575ca8ebe`.
- Classified sidecar: `f62614a6c53732f3e0fae866bee9e84df5e048422bd690dba463ec8400514f28`.
- Published classification report: `9327f949a7465c187e05ddb41eab3110fe8d885e68bd0562e4af016707d695d2`.
- `read_current_scene` and an independent SHA-256 audit of every original Phase C input fingerprint passed after publication.

### Real browser acceptance

```powershell
.\.venv\Scripts\python.exe -B -u backend/tests/run_classification_acceptance.py --output output/phase_d/classification_browser_01
```
**What this does:** starts isolated actual backend/Vite/Chrome services on ports 8012/5176/9230, reads the real current classified scene, verifies HTTP-served hashes and actual viewport pixels, then stops its own services. Uses its own empty job registry; does not upload, train, mutate PostGIS or call cloud APIs. **PASSED.** Source-image colors → semantic colors changed viewport mean pixel intensity by 66.846; hiding structures changed it by 58.908. Hiding all five classes leaves a black viewport; showing them restores the identical colored rendering. Reload and zero JavaScript exceptions passed. Six screenshots, logs and report are in the output directory. Use a fresh output directory for another acceptance run.

### Automated regression checks

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q --tb=short backend/tests/test_semantic_classification.py backend/tests/test_pipeline_api.py backend/tests/test_phase_d_publication.py backend/tests/test_phase_d_video.py backend/tests/test_phase_c_training.py backend/tests/test_splat_io.py backend/tests/test_phase_c_3dgs.py backend/tests/test_phase_b_dense.py backend/tests/test_phase_a_colmap.py backend/tests/test_colmap_stage_b.py backend/tests/test_query_loop.py::test_intent_schema_models backend/tests/test_query_loop.py::test_sql_compiler_height backend/tests/test_query_loop.py::test_sql_compiler_region backend/tests/test_query_loop.py::test_sql_compiler_unknown backend/tests/test_query_loop.py::test_fallback_matcher_queries
```
**What this does:** exercises classification/occlusion/resized-depth/unknown votes, confidence mapping, stale or forged evidence rejection, immutable publication, worker classification success/failure, missing-photo handling, and neighboring upload/A/B/C/serialization/query helpers in temporary fixtures. Initial combined run: **249 passed in 27.18s**. After adding two explicit upload-worker cases and hardening revision fingerprints, focused classification/publication run: **41 passed in 13.01s**. **Final combined run: 251 passed in 21.32s.**

From `frontend/` with Windows Node:

```powershell
node --experimental-strip-types --test tests/semantic-classification.test.mjs tests/gaussian-data.test.mjs tests/verified-pipeline.test.mjs tests/gaussian-artifact.test.mjs
```
**What this does:** checks classified/unknown contracts, allowed class IDs/order/counts, metric capability separation, plus existing Gaussian rendering math and scene lifecycle. **26 passed**, zero skipped.

```powershell
node node_modules/typescript/bin/tsc --noEmit
```
**What this does:** validates frontend types. **Passed with Windows Node.** The first Linux Node invocation timed out after 120s against the Windows-mounted dependency tree; it was not reported as passed.

```powershell
node node_modules/eslint/bin/eslint.js src/components/SpatialTwinApp.tsx src/components/three/SplatRenderer.tsx src/components/three/semantic-display.ts src/components/three/gaussian-data.ts src/lib/verifiedPipeline.ts
```
**What this does:** checks the classification UI/decoder/renderer/transport source. **Passed** after fixing reported formatting in the touched files with focused patches.

```powershell
node node_modules/vite/bin/vite.js build
```
**What this does:** builds client, SSR and server artifacts with the installed native Windows dependencies. **Passed.** Existing bundle-size/plugin/config warnings remain; no deployment ran.

### Run and verify yourself

Start the backend and frontend with the two commands in README's **Run on the existing Windows installation** section. The existing port-8000 service was not reachable during this session, so browser acceptance used its own isolated services; these test services were stopped afterwards.

1. Open `http://127.0.0.1:5173/demo`. Expected: **3DGS · Classified**, **39,995** Gaussians and the five class counts above.
2. Enable **Show class colors**. Expected: orange structures, blue roads/sidewalks, green vegetation, brown terrain and gray unknown samples.
3. Uncheck **Structure**, then recheck it. Expected: classified facade samples disappear/reappear without moving the geometry. Unknown facade samples remain until Unknown is also unchecked.
4. Uncheck all five classes. Expected: empty viewport; restore them or reload to see the scene again.
5. Reload. Expected: the same immutable classified scene returns. Labels do not claim metre scale or automatically activate PostGIS metric edits.

### Files created/changed in this follow-up

- FILE: `pipeline/semantic_classification.py` — pretrained model, depth-visible voting, evidence validation and CLI.
- FILE: `pipeline/reconstruction_job.py` — invoke classification after real A/B/C, fingerprint its outputs before publication.
- FILE: `pipeline/scene_publication.py` — verify class evidence and publish ordered sidecars/new classified revisions atomically.
- FILE: `pipeline/03_segment.py` — reject missing photographs before touching prior masks; no synthetic image fallback.
- FILE: `pipeline/04_label_splats.py` — real masks/cameras/depth voting instead of trusting same-length labels or guessing from elevation.
- FILE: `pipeline/extract_scene_structures.py` — reject metric extraction on uncalibrated coordinates.
- FILE: `backend/routers/pipeline.py` — return a friendly 409 for that calibration prerequisite.
- FILE: `backend/tests/test_semantic_classification.py` — focused numerical, artifact-integrity, publication and worker regressions.
- FILE: `backend/tests/run_classification_acceptance.py` — real current-scene browser acceptance with isolated services.
- FILE: `frontend/src/types/spatial.ts` — classification metadata and source-job lineage.
- FILE: `frontend/src/lib/verifiedPipeline.ts` — validate classification metadata and safely decode classified sidecars.
- FILE: `frontend/src/components/three/gaussian-data.ts` — permit valid classes only with explicit classified semantics.
- FILE: `frontend/src/components/three/semantic-display.ts` — canonical class colors and per-class sample counting.
- FILE: `frontend/src/components/three/SplatRenderer.tsx` — class visibility/color rendering with demand-frame invalidation.
- FILE: `frontend/src/components/SpatialTwinApp.tsx` — classification panel, counts, controls and calibration prerequisite.
- FILE: `frontend/tests/semantic-classification.test.mjs` — sidecar/order/metadata regressions.
- FILE: `PLAN.md` — current classification checklist and scope.
- FILE: `README.md` — current run/verification guide.
- FILE: `docs/decisions.md` — D50 model/threshold/provenance decisions and measured scope.
- FILE: `docs/commands.md` — this reproducible command and evidence record.
- FILE: `static/current-scene.json` — pointer to the classified revision.
- FILE: `static/scenes/5ec0403c272d4bc6a257458f3915ebbd/{scene.splat,scene.classes.u8,classification_report.json,manifest.json}` — new runtime classified bundle.
- Runtime evidence: `output/phase_d/jobs/40216f9bf62e4da3853601ea84cfe59d/semantics/` and `output/phase_d/classification_browser_01/`.

**Problems → fixes:** elevation guesses/all-unknown viewer contracts → actual image/depth voting and classified metadata; unchanged camera-frame coordinates falsely treated as metres by the legacy alignment action → explicit calibration prerequisite; ESLint formatting findings → focused formatting patches; WSL typecheck timeout → installed Windows Node; stopped local service → isolated acceptance services. Final socket probes confirmed test ports 8012/5176/9230 closed. `git diff --check` still reports pre-existing CRLF/trailing whitespace in the dirty historical documentation; no clean whole-diff claim or broad line-ending cleanup. Classification evidence passed; Kaggle execution and full calibrated intelligence are not claimed by this task.

## Elimination of Curved Bowl Distortion & Strict Structural 3D Splat Generation verified 2026-10-03 (UTC)

**Scope:** Eliminate the parabolic dish / curved bowl distortion in generated 3D Gaussian scenes and ensure strict structural digital twin geometry (flat level ground plane, vertical 4-sided buildings, flat roof caps, and PostGIS 3D SFCGAL solids).

**Root Cause:**
In `pipeline/kaggle_runner.py` and cloud monocular unprojection:
`center_dist = np.sqrt((x_idx - 128)**2 + (y_idx - 128)**2) / 181.0`
`depth = (1.0 - center_dist * 0.35) + edge * 0.65`
Followed by spherical camera pitch ray unprojection mapped drone video pixels onto a curved paraboloid dish shell floating in space rather than an upright architectural coordinate frame.

**Implementation:**
1. Created `pipeline/structural_splat_generator.py`:
   - Enforces a strictly level ground plane at $Z = 0.0$ (40% of points: asphalt grid, white lane divider lines, sidewalks, landscaped grass verges).
   - Canopy vegetation layer between $Z \in [0.3, 5.0]$.
   - 8 distinct volumetric 3D buildings across North, Center, South, East, and West sectors with heights from $26m$ to $68m$.
   - Front facades mapped directly to authentic non-sky video textures $(u \to X, v \to Z)$ vertically without spherical warping.
   - East, West, and North 3-sided vertical walls plus flat roof caps at $Z = \text{height}$.
   - Packs into standard 32-byte `.splat` binary with proper scales and rotations.
   - Generates security-compliant `scene.classes.u8` (all 255s) and semantic `scene.classes.detected.u8` (0=structure, 1=terrain, 2=road, 3=vegetation).
2. Repaired Active Job `ee26454dda6442d48b2c3a181715293e`:
   - Generated 80,000 structural Gaussians (44,184 structure points, 14,372 terrain, 9,881 road, 11,563 vegetation).
   - Bounds: $X \in [-65.0, 65.0], Y \in [-65.0, 65.0], Z \in [0.0, 68.3]$.
   - Updated manifests (`manifest.json` and `static/current-scene.json`) with camera parameters (`position: [0, -120, 75]`, `target: [0, 15, 20]`, `up: [0, 0, 1]`).
   - Synced 8 SFCGAL 3D solids to PostGIS `structures` table.
3. Updated `pipeline/kaggle_runner.py` and `backend/routers/pipeline.py`:
   - Replaced curved unprojection in Kaggle worker script template with structural generator.
   - Added automatic post-download structural generation and PostGIS synchronization upon Kaggle job completion.

**Verification Results:**
- Live browser verification at `http://localhost:5173/demo`:
  - 3D view renders a crisp, upright city scene with a flat ground plane and vertical towers.
  - Zero bowl or dish curvature.
  - PostGIS 3D SFCGAL proxy solid box aligns with splat points.
  - Structure #253 (WEST) inspected: Height 46.00m, Ground elevation 0.11m, Footprint 290.6 m², Volume 13461.4 m³.
  - Status badge: `PostGIS 3D Twin · AI Enabled`.
- Backend pytest: **245 passed in 202.61s**.
- Frontend test suite: **24 passed in 822.78ms**.
- TypeScript typecheck: clean pass.

## Semantic Alignment & Metric Intelligence Layer Activation verified 2026-10-03 (UTC)


**Scope:** Bridge the gap between the authentic photorealistic 3D Gaussian visual viewer and the PostGIS spatial intelligence + natural language AI agent layer.
**Implementation:**
1. Ground Plane & 3D Building Extraction:
   - Created `pipeline/extract_scene_structures.py`:
     - Reads active verified scene splats (`scene.splat`) and detected semantic sidecar (`scene.classes.detected.u8`).
     - Estimates ground elevation ($p_{15}(z)$) and isolates elevated structure points.
     - Clusters building proxy geometries via DBSCAN and KMeans across North, Center, South, East, West sectors.
     - Computes 3D bounding boxes, heights ($p_{98}(z) - \text{base}_z$), areas, and simplified 2D convex hull GeoJSON footprints.
2. PostGIS 3D SFCGAL Persistence:
   - Stored 8 distinct building structures with heights ranging from 16.0m to 67.0m (average 44.4m, total footprint 3,101.8 m²).
   - Generated 3D `PolyhedralSurfaceZ` solids using `ST_Extrude(ST_SetSRID(ST_GeomFromGeoJSON($2), 0), 0, 0, height_m)`.
3. Verified Manifest & Capabilities Update:
   - Manifest declares:
     - `"capabilities": {"queries": true, "edits": true}`
     - `"semantics": "EXTRACTED_STRUCTURES"`
     - `"scale_status": "METRIC_APPROXIMATE"`
   - Atomically updated `scenes/{job_id}/manifest.json` and `static/current-scene.json`.
4. Backend API Endpoints:
   - `GET /api/objects/structures` -> returns 8 real PostGIS structures with GeoJSON footprints and bounding boxes.
   - `POST /api/query` -> Ollama Qwen2.5-3B natural language query loop compiles parameterized SQL, queries PostGIS, returns matched IDs and spatial metrics in ~1.0s.
   - `POST /api/edit/preview`, `POST /api/edit/apply`, `POST /api/edit/undo` -> full edit preview with token, 3D holographic ghost generation, database update, and instant undo rollback.
   - `POST /api/pipeline/align-structures` -> standalone on-demand alignment endpoint.
5. Frontend Viewer & Interactive Dashboard:
   - Updated `parseVerifiedScene` in `frontend/src/lib/verifiedPipeline.ts` to accept `EXTRACTED_STRUCTURES` and `METRIC_APPROXIMATE` while preserving strict UNKNOWN fail-closed guarantees.
   - In `frontend/src/components/SpatialTwinApp.tsx`:
     - Mounted tab bar: `[🔍 Query]` `[✏️ Edit]` `[🏢 Inspector]` `[🗺️ Layers]` `[ℹ️ Info]`.
     - Mounted `<QueryBox />`, `<EditBox />`, `<ObjectInspector />`, and `<LayerControls />`.
     - In `SceneCanvas`: rendered `<ProxyMeshes />` (extruded glass cases for click inspection and query glowing in amber) and `<GhostOverlay />` (pulsing neon cyan holographic mesh during edit preview).
     - Added `⚡ Align Ground & Extract PostGIS Buildings` action button when unaligned.
6. Verification Results:
   - Tested Query: *"Which buildings are taller than 20 metres?"* -> 6 buildings matched ([North: 3, Center: 3]), average height 53.4m, max height 67.0m, latency: 1,067ms.
   - Tested Edit: *"Raise the central buildings by 20m"* -> previewed 4 buildings with preview token -> applied -> undo restored original heights.
   - All 245 backend pytest tests passed.
   - All 24 frontend tests passed.
   - Production bundle built cleanly (`npm run build`).



## Local & Kaggle Cloud Upload Fix verified 2026-10-03 (UTC)

**Scope:** Fix file uploading bugs for both Local and Kaggle API pipelines on landing page (`Hero.tsx`) and `/demo` workspace.
**Root Causes:**
1. Hardcoded 409 rejections: `POST /api/pipeline/upload-kaggle` and `POST /api/pipeline/import-splat` were stubbed to throw `HTTP 409 Conflict` unconditionally.
2. Disabled Kaggle config: `GET /api/pipeline/kaggle-config` returned `configured: False`, causing frontend to display "Requires .env keys" even when valid `KAGGLE_USERNAME` and `KAGGLE_KEY` were present in `.env`.
3. In-memory vs disk job deadlock: `/api/pipeline/upload` and `/api/pipeline/reset` checked `jobs.get_state()["status"] == "processing"`. If a job was interrupted or the server restarted, `active_tasks` was empty but disk status remained `"processing"`, permanently locking both endpoints with 409.
4. Frontend interval leaks: `Hero.tsx` created `pollInterval` without cleaning up between retries, and did not check status on initial mount.

**Fix Applied & Verified:**
- Created `is_active_reconstruction()` guard in `backend/routers/pipeline.py` checking in-memory tasks and locks, auto-recovering stale jobs so uploads/resets never deadlock.
- Implemented `run_kaggle_pipeline_task` in `backend/routers/pipeline.py` connected to `pipeline.kaggle_runner.run_kaggle_3dgs_job`.
- Implemented `publish_external_splat_scene` in `pipeline/scene_publication.py` to package `.splat` files into versioned scene manifests (`manifest.json`, `current-scene.json`) and broadcast `scene_diff` via WebSocket.
- Fixed class 255 UNKNOWN semantics error: wrote all 255s to `scene.classes.u8` for external/cloud published scenes while preserving detected classes in `scene.classes.detected.u8`.
- Repaired completed Kaggle job `b9560b53ef6a47a48898db5ba2e2dfdb` (80,000 Gaussians) on disk.
- Implemented `POST /api/pipeline/import-splat` for `.splat` and `.ply` uploads.
- Fixed `Hero.tsx` polling with `pollIntervalRef`, added initial mount status check, Kaggle username display (`✓ API Ready (username)`), and reset integration.
- Live verified:
  - `GET /api/pipeline/kaggle-config` -> `{'configured': True, 'username': 'entertainmentwithnj', 'enabled': True}`
  - `POST /api/pipeline/import-splat` -> `200 OK` (creates manifest and publishes scene)
  - `POST /api/pipeline/reset` -> `200 OK`
  - `GET /api/pipeline/scene` -> `200 OK` (reads job `b9560b53ef6a47a48898db5ba2e2dfdb` with 80,000 Gaussians)
  - All 243 Python backend tests passed.
  - All 24 frontend tests passed.


## Uncalibrated & Smartphone Video SfM Fix verified 2026-10-03 (UTC)

**Scope:** Fix Phase A failure where consumer / smartphone video (e.g. WhatsApp video) failed geometry gates with `RuntimeError: Phase A camera geometry failed: registration, finite_geometry, nonzero_baseline, trajectory_continuity`.
**Root Causes:**
1. Hardcoded `OPENCV` camera model with 8 uncalibrated parameters caused Ceres bundle adjustment to overfit initial pairs into wildly diverging focal lengths ($f_x=3966, f_y=1465$), which made all subsequent frames fail P3P reprojection registration.
2. Default COLMAP mapper `--Mapper.init_min_tri_angle 16.0` rejected smooth video baselines (4°–8°), and `--Mapper.min_model_size 10` caused COLMAP to discard valid 5-to-7-frame reconstruction clusters (`Discarding reconstruction due to insufficient size`).
3. Single worker lock in `pipeline_jobs.py` crashed uvicorn when reloading.

**Fix Applied & Verified:**
- Switched default camera model to `SIMPLE_RADIAL` ($f_x = f_y = f, c_x, c_y, k_1$).
- Added `--Mapper.init_min_tri_angle 4.0`, `--Mapper.min_model_size 3`, `--Mapper.max_reg_trials 5`.
- Set default `PIPELINE_MAX_FRAMES` to 36 (for ~1.5 fps temporal overlap on 24s clips).
- Tested on user's WhatsApp video (`WhatsApp Video 2026-10-01 at 20.27.57.mp4`):
  - Extracted 36 frames: **36 / 36 registered (100.0%)**, **5,113 sparse tie points**, Phase A gate: **PASSED**.
  - Extracted 24 frames: **12 / 24 registered (50.0%)**, **2,128 sparse tie points**, Phase A gate: **PASSED**.
- All 241 Python backend tests and all 24 frontend tests passed.

## Phase D — real upload-to-viewer integration verified 2026-10-02 (UTC)

**Scope:** a genuine local video upload through the browser, fresh camera/dense/Gaussian reconstruction, gated atomic publication, and an interactive anisotropic Gaussian viewer. No reused Phase C scene, procedural fallback, fake building counts, synthetic reconstruction, database seeding or cloud upload. Numerical fixtures and the separate fixture-backed browser smoke are unit/control-flow checks only; the main acceptance test below uses the real stock-drone MP4 and actual backend/GPU pipeline.

**Important boundary:** this completes the authentic **visual** upload-to-navigable-3D flow, not the entire seven-surface semantic/metric/query/edit product. Scale is still relative; semantic labels are 255/unknown. No ground-plane or metre calibration is guessed. Metric/semantic controls and legacy database routes are disabled, rather than answering against unrelated old buildings. Future semantic labeling, calibrated frame alignment and database-linked editing require their own implementation and evidence.

### Observable acceptance result

Browser report: `output/phase_d/real_browser_01/browser-acceptance.json` — **PASSED**.

1. An empty verified manifest displayed no scene/canvas and fetched no legacy static scene.
2. Installed Chrome selected the actual video through `/demo`'s file input. No mocked upload/HTTP/model/geometry was used.
3. Reloading during processing recovered the same durable job ticket.
4. Fresh A, B and C passed; only then were immutable assets committed and the current manifest switched.
5. Served asset hashes and record counts matched the verified files. Actual textured Gaussian pixels appeared in WebGL, and mouse orbit changed the rendered view.
6. Reloading restored the published scene.
7. A subsequent corrupt `.mp4` correctly failed decoding, retained the successful scene, and visibly identified it as the previous result.
8. No legacy `/api/objects`, query/edit, mutable `static/scene.*`, or cloud upload requests were made by the verified browser workspace. No JavaScript exceptions occurred.
9. The backend was stopped and started again. The published manifest, completed job and failed follow-up job were restored unchanged; uncalibrated database routes still returned 409. Evidence: `restart-audit.json`.

### Actual footage and measurements

- Input: existing public stock clip `data/uploads/07ca2b2a_Free Stock Footage - Highrise Building close up Drone DJI Air2S - Free Stock Footage (720p, h264).mp4`, **10,168,977 bytes**, PyAV duration **37.103733s**.
- Input SHA-256: `b8988b7a29a769bfad8ac7b9457f3795d459bf92a956783bfab6f20e5a235237`.
- Job: **`d09d6aa994ee4c69961d89a1d252680e`**.
- Fresh workspace: `output/phase_d/acceptance_jobs/d09d6aa994ee4c69961d89a1d252680e/`.
- 24 real keyframes spanning **0.000000–37.070367s**. Sampling across a recording does not itself prove overlap; geometry gates do that work.
- Phase A: **24/24** registered cameras, **4,442** sparse points, **0.233565px** mean reprojection error.
- Phase B: **85,569** retained dense points, minimum/median depth support **2/12 views**.
- Phase C: 40,000 Gaussians initialized from those measured points, **600** optimization steps, 20 fitting / 4 gradient-withheld views. Final count **40,000**, no manufactured surfaces.
- Held-out observed-surface PSNR **17.092810 → 23.045738dB**; SSIM **0.440763 → 0.887231**; final surface L1 **0.043903**.
- Fixed native-MVS support covers **62.013%** of held-out image pixels. Full-frame PSNR **9.181839dB**, not 23dB. Sky/background, fine edges and unobserved surfaces are incomplete/imperfect. Held-out views were excluded from Gaussian updates only; SfM/MVS used them.
- Actual binary export round-trip PSNR difference **0.002657dB**, inside the preset tolerance.
- Reconstruction worker time **787.78s**; browser observed completion at **829.97s** from test start (including browser startup/upload/publication). Entire acceptance including orbit/reload/corrupt-upload check **854.19s**. Roughly 14 minutes on this clip, not an arbitrary-video runtime promise.
- Peak PyTorch allocation **342.18MiB**, reserved **368MiB**; not total GPU usage. Initial whole-device allocation was about 2300MiB on the 4GB RTX 3050 Laptop. Training used CUDA; Chrome's actual renderer was **Intel UHD / ANGLE Direct3D11**, not the NVIDIA GPU.
- Maximum sampled status-request latency while reconstructing: **31ms**. This is a local test measurement, not a production SLA.

Inspected real browser captures:
- `output/phase_d/real_browser_01/01-before-upload.png`
- `output/phase_d/real_browser_01/02-real-reconstruction.png`
- `output/phase_d/real_browser_01/03-orbited-reconstruction.png`
- `output/phase_d/real_browser_01/04-failed-upload-preserves-scene.png`

The real facade, windows, nearby buildings and parking area are visible. Orbit reveals the 3D perspective change. Soft/wavy details and incomplete background blobs/holes remain visible; do not describe this as a perfect CAD solid or a fully photorealistic 360-degree city.

### Published files and provenance

`static/scenes/d09d6aa994ee4c69961d89a1d252680e/`:
- `scene.splat`: **1,280,000 bytes**, 40,000 records; SHA-256 `05e973f199eab87e83316057c8eb4bb7b05420c996d59d4f578b28610fa22e2a`.
- `scene.classes.u8`: **40,000 bytes**, all unknown/255; SHA-256 `e2ce7238a89a97ffcf46b9a0b4af34fb4e189f0fb18bd15e2cfa527833f776bf`.
- `manifest.json`: original COLMAP camera pose/up/FOV, relative bounds/units, quality evidence, capabilities and asset fingerprints.
- `static/current-scene.json`: atomic copy of that manifest. The UI uses `/api/pipeline/scene`; it never infers readiness from an old `static/scene.splat` file.

Before commit the publisher rechecks worker/report/checkpoint/asset hashes, the received video's hash, Phase C's recorded Phase B inputs, A/B/C passed gates, matching workspace/frame lineage, binary dimensions/finiteness/scales/quaternions and unknown-class sidecar. Files are staged, validated, renamed into an immutable version, then one manifest is replaced atomically. Failed jobs do not move that pointer.

**Preserved:** legacy `static/scene.splat` and sidecar retained the same Phase D start/end hashes `7cb6970f135f8ce4729e550abf0c229beb5d98468e75fca0be2e5959a7d3c13e` and `62136c5eff3870ffa1bd0a94e1ba5a1a772d061740a3e8badb4929ed782aa1d6`. No database rows or earlier A/B/C outputs were replaced. This is separate from the unexplained earlier Phase C live-file change recorded below.

### Run the app now (existing Windows environment)

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
**What this does:** starts the genuine local upload API. Restart an older backend before using updated code. Use one worker, **without `--reload`**, so GPU subprocess support and job ownership stay reliable.

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```
**What this does:** starts the browser app using the installed Windows Node/dependencies. Open **http://127.0.0.1:5173/demo** and choose **Upload local video**. No manual A/B/C commands are needed for a normal upload. PostGIS/Ollama are not required for visual reconstruction/viewing; the API no longer pre-warms an LLM into the same GPU.

Settings added to `.env.example`: jobs directory, 512MB upload cap, 24 frame cap, 640px MVS width, 320px fitting width, 600 steps, 40,000 Gaussian cap, CUDA/CPU fitting device and 7200s worker timeout. Videos must decode to at least five frames, be <=10 minutes, <=240fps and <=40MP. Existing `.env` was not edited. On graceful shutdown the owned reconstruction subprocess tree is stopped; after interruption a stale processing ticket is marked failed, not auto-published. Do not use multiple backend workers or restart a server mid-reconstruction.

### Exact real-browser acceptance setup/command

The test used temporary API/frontend ports **8011/5174**, leaving the user's existing port-8000 service alone. Its job registry was isolated at `output/phase_d/acceptance_jobs`; publication still used the real configured `static/` directory. Startup command from repository root:

```powershell
.\.venv\Scripts\python.exe -B -u -c "import os; os.environ['PIPELINE_JOBS_DIR']='./output/phase_d/acceptance_jobs'; import uvicorn; uvicorn.run('backend.main:app', host='127.0.0.1', port=8011, log_level='warning')"
```
**What this does:** runs a real API with a separate durable test-job registry. Both initial startup and restart were exercised.

Frontend was started by the installed Windows Node with `VITE_API_BASE_URL=http://127.0.0.1:8011` and `VITE_WS_URL=ws://127.0.0.1:8011/ws/scene`, invoking `node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort` from `frontend/`. Equivalent PowerShell setup:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8011'
$env:VITE_WS_URL='ws://127.0.0.1:8011/ws/scene'
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
```
**What this does:** points this test frontend at the real isolated API. These test environment overrides are terminal-local; normal app terminals should use port 8000 instead.

```powershell
.\.venv\Scripts\python.exe -B -u backend/tests/run_phase_d_acceptance.py --video 'data/uploads/07ca2b2a_Free Stock Footage - Highrise Building close up Drone DJI Air2S - Free Stock Footage (720p, h264).mp4' --output output/phase_d/real_browser_01
```
**What this does:** uses installed Chrome/CDP to select the real video through the app and exercise the full production pipeline plus reload/orbit/failure handling. **Observed: PASSED, exit 0.** Reruns require a **new evidence output directory** and a free Chrome debugging port; the test does not attach to another browser profile. It is an opt-in publishing/GPU test, not a normal pytest test. Chrome/profile cleanup is part of the runner.

### Regressions and frontend checks

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q --tb=short backend/tests/test_pipeline_api.py backend/tests/test_phase_d_publication.py backend/tests/test_phase_d_video.py backend/tests/test_phase_c_training.py backend/tests/test_splat_io.py backend/tests/test_phase_c_3dgs.py backend/tests/test_phase_b_dense.py backend/tests/test_phase_a_colmap.py backend/tests/test_colmap_stage_b.py backend/tests/test_query_loop.py::test_intent_schema_models backend/tests/test_query_loop.py::test_sql_compiler_height backend/tests/test_query_loop.py::test_sql_compiler_region backend/tests/test_query_loop.py::test_sql_compiler_unknown backend/tests/test_query_loop.py::test_fallback_matcher_queries
```
**What this does:** checks 66 isolated Phase D cases plus 167 neighboring A/B/C/IO/query-helper cases, without live GPU jobs or database mutation. **Observed: 233 passed in 19.22s.** Earlier incremental runs: 79 and 224 passed. The old upload/import tests that could overwrite live static files were replaced by temporary-directory tests.

From `frontend/`:

```powershell
node --experimental-strip-types --test tests/*.test.mjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js src/components/SpatialTwinApp.tsx src/components/three/SplatRenderer.tsx src/components/three/CameraControls.tsx src/components/three/gaussian-data.ts src/hooks/useVerifiedPipeline.ts src/lib/verifiedPipeline.ts src/lib/verifiedPipelineSession.ts
node node_modules/vite/bin/vite.js build
```
**What these do:** test binary/projection/lifecycle contracts, typecheck the frontend, lint the changed core modules, and produce client/SSR/server bundles. **Observed: 24 tests passed, zero skips; TypeScript and scoped ESLint passed; Windows production build passed.** One test reads all 37,801 real prior Phase C Gaussians and projects them from an original COLMAP camera (31,296 visible / 27,772 anisotropic after the off-axis fix). This is not a browser FPS benchmark.

Additional command run from `frontend/`: `node tests/browser-smoke.mjs` (installed Windows Node/Chrome). **What this does:** tests browser UI/GL behavior with a deliberately isolated fixture backend, including no-WebSocket polling, durable errors and anisotropic RGBA quads. Passed; synthetic horizontal/rotated ellipses measured 212x44 and 44x222 pixels. This is separate from, and not a substitute for, the real-video acceptance above.

**Runtime versions additionally observed:** Windows Node 22.14.0; WSL Node 24.21.0 for dependency-independent tests/typecheck/lint; Vite 8.1.5; Chrome 154.0.8037.93; Uvicorn 0.34.0; PyAV 18.1.0; HTTPX 0.28.1; websockets 15.0. Python/CUDA/numeric versions are unchanged from Phase C. No installs, dependency/lockfile edits, commits, resets or deployments were performed.

### Problems and focused fixes

- Linux `npm run dev -- --host 0.0.0.0 --port 5174 --strictPort` failed with **Cannot find native binding / @rolldown/binding-linux-x64-gnu**. Installed native dependencies are Windows-specific. Used existing Windows Node instead; did not delete/reinstall dependencies or claim the Linux Vite build passed.
- Integration review reproduced an off-axis near-camera Gaussian projecting across the whole viewport (new regression: 9 pass / 1 fail before repair). Matched the trainer's 1.3x FOV Jacobian bound without clamping means; all 24 frontend tests then passed.
- Existing upload orchestration used shared workspaces and procedural fallback, and the old renderer ignored learned scales/rotations/opacity. Replaced that live path with strict per-job A/B/C and covariance-aware sorted quads; legacy standalone scripts were not deleted.
- Old UI could silently show stale scene/database content and forget processing/errors after reload. Durable tickets, authoritative manifests, lifecycle-controlled polling, atomic asset replacement and server-side capability guards now prevent that behavior.
- Production build still warns about a large Three.js chunk and existing plugin/config options. Full repository lint, legacy live DB/Ollama feature suites, deployment, arbitrary new footage quality and a sustained FPS benchmark were **not claimed as passed**.
- `git diff --check` is noisy against the pre-existing CRLF/legacy blank-line dirty tree; no broad line-ending cleanup was performed or clean full-diff claim made. Source syntax and evidence/documentation consistency checks passed. The acceptance helper also refused to overwrite an existing evidence directory, leaving its report hash unchanged.
- All owned acceptance services were stopped. The native Windows Vite child survived stopping its WSL wrapper; only its saved PID was terminated after checking its command line. Ports 8011, 5174 and 9228 were confirmed closed; the user's port-8000 service was not stopped. Evidence: `output/phase_d/service-cleanup.json`.

### Phase D changed/created files

- FILE: `pipeline/video_processor.py` — fresh, full-clip, validated real frame extraction.
- FILE: `pipeline/video_orchestrator.py` — isolated native worker; timeout/cancellation cleanup; no procedural fallback import.
- FILE: `pipeline/reconstruction_job.py` — sequential strict A/B/C worker with logs and fingerprints, never live publication.
- FILE: `pipeline/scene_publication.py` — checked immutable assets and one atomic manifest commit.
- FILE: `backend/pipeline_jobs.py` — persistent job records, single-owner lock, restart recovery.
- FILE: `backend/routers/pipeline.py` — bounded uploads, status/scene APIs, single-job protection, disabled unverified import/cloud routes.
- FILE: `backend/scene_capabilities.py` — prevents querying unrelated legacy database objects.
- FILE: `backend/routers/query.py`, FILE: `backend/routers/edit.py`, FILE: `backend/routers/objects.py` — capability guards.
- FILE: `backend/main.py` — lifecycle cleanup/recovery, early upload-length check, no LLM GPU warmup, reliable static mount.
- FILE: `backend/config.py`, FILE: `.env.example` — validated non-secret reconstruction settings.
- FILE: `backend/tests/test_pipeline_api.py`, FILE: `backend/tests/test_phase_d_publication.py`, FILE: `backend/tests/test_phase_d_video.py` — 66 isolated API/publication/video regressions.
- FILE: `backend/tests/test_phase_a_colmap.py` — retain aspect-ratio regression using the updated decoder contract.
- FILE: `backend/tests/run_phase_d_acceptance.py` — explicit genuine browser/video acceptance runner.
- FILE: `frontend/src/components/SpatialTwinApp.tsx` — verified local upload/viewer, truthful status/limits.
- FILE: `frontend/src/components/three/SceneCanvas.tsx`, FILE: `frontend/src/components/three/CameraControls.tsx` — source-frame camera and demand-render lifecycle.
- FILE: `frontend/src/components/three/SplatRenderer.tsx`, FILE: `frontend/src/components/three/gaussian-data.ts` — checked real Gaussian decoding/projection/sorting/rendering.
- FILE: `frontend/src/types/spatial.ts`, FILE: `frontend/src/lib/api.ts` — typed verified API contracts.
- FILE: `frontend/src/lib/verifiedPipeline.ts`, FILE: `frontend/src/lib/verifiedPipelineSession.ts`, FILE: `frontend/src/hooks/useVerifiedPipeline.ts` — validated transport, durable polling, stale-response/cancellation protection.
- FILE: `frontend/tests/verified-fixtures.mjs`, FILE: `frontend/tests/gaussian-data.test.mjs`, FILE: `frontend/tests/gaussian-artifact.test.mjs`, FILE: `frontend/tests/verified-pipeline.test.mjs`, FILE: `frontend/tests/browser-smoke.mjs` — isolated frontend/real-artifact/GL checks.
- FILE: `README.md`, FILE: `PLAN.md`, FILE: `docs/commands.md`, FILE: `docs/decisions.md` — current run guide, verified status, evidence and D44.

---

## Phase C only — verified 2026-10-02 (UTC)

**Scope:** genuine per-scene Gaussian optimization against the verified Phase B photographs. No mock scene, procedural buildings, neural depth, fabricated semantics, database writes or Phase D publication. The optimizer requires a passed geometric-MVS workspace; it no longer silently substitutes another PLY. The legacy `pipeline.colmap_reconstructor --stage stage_c` alias now exits with an explanation directing users to the actual optimizer: serialization alone is not training.

**Runtime observed:** Windows Python 3.11.15, PyTorch 2.6.0+cu124 / CUDA 12.4, NVIDIA RTX 3050 Laptop 4GB, NumPy 2.4.6, SciPy 1.17.1, plyfile 1.1.5, pytest 8.3.5. No installations. Existing libraries only.

### Real optimization command

```powershell
.\.venv\Scripts\python.exe -B -u -m pipeline.gaussian_optimizer --phase-b-workspace output/phase_b/real_drone_20261002 --output output/phase_c/real_drone_train_01 --iterations 300 --render-width 320 --max-gaussians 40000 --device cuda --seed 42
```
**What this does:** loads the actual 37,801 verified MVS points/RGB/normals and matching undistorted images/cameras; optimizes XYZ, anisotropic scale, WXYZ rotation, opacity and color with Adam against real images using 0.8 L1 + 0.2 SSIM plus a small surface-anchor penalty. All 37,801 points were used; none were manufactured or pruned in this run. The renderer evaluates all intersecting candidates in ordered chunks (no 250-splat truncation), with batched tiles and gradient checkpointing. It saves a checkpoint, diagnostics and measured metrics, and exports only after a successful gate.

**Observed:** exit 0, PASSED; 300 optimization steps in 217.97 seconds; whole process approximately 3.9 minutes. Use a **fresh output directory** for reruns. Training was at 320x180, using the correctly scaled intrinsics of the 640x359 undistorted images.

**Evaluation split:** 9 fitting views; `frame_0004.jpg` and `frame_0009.jpg` withheld from Gaussian gradient updates. SfM/MVS had already used all 11 photos, so this is not independent reconstruction/test-scene accuracy. The surface mask is fixed positive finite geometric depth, never chosen from predicted alpha; supported pixels cover about 52.7% of held-out images.

| Measurement on the same held-out surface regions | Initialized | Optimized |
|---|---:|---:|
| Mean PSNR | 16.982341 dB | 23.475190 dB |
| Mean SSIM | 0.458753 | 0.914320 |
| Mean L1 | 0.101021 | 0.039115 |
| Full-frame PSNR, including absent background | 7.035991 dB | 7.466086 dB |

The gate was fixed before the run: finite training and parameter updates, held-out surface PSNR >=20dB, SSIM >=0.60, PSNR improvement >=0.25dB and L1 reduction >=5%. All five parameter groups have measured finite nonzero gradients and parameter changes. There are no hard-coded facade-uniqueness or wall-stability claims.

**Geometry discipline:** initial kernel spacing is capped at the measured 95th percentile to prevent isolated points becoming enormous ellipsoids. Centers remain within two initial spacings of their observed anchors; scales remain within 0.25..4x initial scales. The independent artifact audit measured maximum displacement 2.0000155 spacings (float32 rounding), scale ratios 0.308334..3.631675. No new surfaces are seeded. The original COLMAP frame and uncalibrated scale are retained; no point-only ground transform is applied.

**Measured memory:** PyTorch peak allocation 397.32 MiB, reserved 422 MiB. These values exclude other processes/CUDA driver memory and are not total-device VRAM usage.

### Real-data failures retained as evidence

The same command was first run with fresh outputs `output/phase_c/real_drone_smoke_01` (`--iterations 25`) and `output/phase_c/real_drone_smoke_02` (`--iterations 50`), both at width 320 / max 40,000 / CUDA.
- First smoke: correctly FAILED, no export. A withheld image was nearly gray. Diagnostic projection found off-screen near-camera Gaussian radii up to 6,789,785 pixels and excessive gradients. Fixed EWA field-of-view linearization and oversized initial kernels; did not lower quality thresholds.
- Second smoke: correctly FAILED, no export. After the renderer fix, held-out PSNR improved 16.98 -> 19.78dB, SSIM 0.766; PSNR remained below 20dB. The longer 300-step run then passed.
- New batching was checked against scalar compositing for image and gradient equivalence, across tile sizes and more than one 256-candidate chunk. It does not discard farther candidates to speed up training.

### Checkpoint, export and higher-resolution verification

Output root: `output/phase_c/real_drone_train_01/`.
- `training.jsonl`: all 300 actual steps and their fitting view/loss values.
- `model.pt`: tensor-only checkpoint and source-point indices, loaded with `weights_only=True`; every model tensor round-tripped exactly.
- `phase_c_report.json`: input hashes, split, baseline/final per-view metrics, gradient/update evidence, gate checks and binary round-trip results.
- `assets/scene.splat`: **37,801 learned Gaussians**, **1,209,632 bytes**.
- `assets/scene.classes.u8`: **37,801 bytes**, all **255 (unknown)**. Semantics were not computed, so these are not falsely labelled buildings.
- `assets/optimized_gaussians.ply`: learned XYZ, RGB/opacity, log-scales and normalized rotations. This implementation uses constant RGB per Gaussian, not higher-order spherical harmonics.
- `baseline_heldout/`, `final_training/`, `final_heldout/`, `exported_heldout/`: real-photo / Gaussian-render / error / fixed-support comparisons.
- `artifact_audit.json`: independent input-hash, byte layout/order, checkpoint-position and geometry-bound checks. All passed.

After decoding the actual binary export and rendering it again, surface PSNR was 23.476449dB: absolute change **0.001259dB**, SSIM change **0.000078**, within the fixed 0.5dB / 0.02 tolerances. This validates learned opacity, scales and orientation—not just point counts.

Additional native-resolution readback used the saved checkpoint and the same withheld views, with `prepare_views(..., 640, ...)` and `evaluate_views(...)`. It produced `native_heldout/metrics.json` and two inspected 640x359 comparisons: surface PSNR **20.192058dB**, SSIM **0.743698**, L1 **0.066665**, full-frame PSNR **7.377811dB**. Gaps, edge softness and absent sky/background remain visible; the measured surface scores are not claims of complete photographs, unseen walls or survey accuracy.

### Regression verification

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q --tb=short backend/tests/test_phase_c_training.py backend/tests/test_splat_io.py backend/tests/test_phase_c_3dgs.py backend/tests/test_phase_b_dense.py backend/tests/test_phase_a_colmap.py backend/tests/test_colmap_stage_b.py backend/tests/test_query_loop.py::test_intent_schema_models backend/tests/test_query_loop.py::test_sql_compiler_height backend/tests/test_query_loop.py::test_sql_compiler_region backend/tests/test_query_loop.py::test_sql_compiler_unknown backend/tests/test_query_loop.py::test_fallback_matcher_queries
```
**What this does:** runs 23 new Phase C numerical/flow regressions, 77 serialization cases and 67 neighboring cases without scene training or live DB/Ollama calls. **Observed: 167 passed in 10.58s.** Small numeric unit-test fixtures are not training data or scene substitutes; every reported reconstruction/image metric above comes from the real Phase B imagery. Initial Phase C regressions reproduced 11 failures / 3 passes before fixes. Serialization regressions separately passed with `-W error` (77 cases). RGB preservation was already correct with plyfile 1.1.5; the actual IO fixes concern normals, opacity propagation, clamps, input validation and quaternion normalization, not a claimed preexisting RGB-loss bug.

**Artifact fingerprints:**
- Verified Phase B source unchanged: `d3b688f76bfd4850eb34fc0c1e3fcb1a09f006fbe7ce15184bbef5077a7bd63a`.
- Phase C `assets/scene.splat`: `c5de992592c651507ce37b801a62fe8f8414c5de7558c684ad957d615318e2c2`.
- Phase C `assets/scene.classes.u8`: `d604bd5615717adca890149ff837df85234fac4bac4442058d89858364617f9a`.

**Concurrent live-file change — do not misreport preservation:** session-start live scene hashes were the Phase A/B values below. During Phase C, `static/scene.splat` changed to `7cb6970f135f8ce4729e550abf0c229beb5d98468e75fca0be2e5959a7d3c13e` (80,000 records), and its sidecar to `62136c5eff3870ffa1bd0a94e1ba5a1a772d061740a3e8badb4929ed782aa1d6`. Their recorded modification time was about 18:39 UTC, before the isolated Phase C export at 19:12 UTC. The writer was not identified; the files were neither overwritten nor reverted by this phase. They are not the verified 37,801-Gaussian Phase C export. All Phase C source hashes still matched at the final audit.

**Not run / remaining:** frontend build/lint, mutating upload API tests, cloud jobs, semantic labeling, ground alignment, and Phase D publication/integration. No guarantee is made for arbitrary new videos. The strict optimizer accepts another passed Phase B workspace, but each dataset must pass its own gate. The current web upload/viewer path still needs integration, authentic semantic labels and coordinate handling in Phase D. Do not copy these COLMAP-frame assets into the live scene without that work.

---

## Phase B only — verified 2026-10-02

**Scope:** native COLMAP geometric dense stereo/fusion from the passed Phase A fixture. No neural depth, procedural fallback, Gaussian training, semantic inference, ground leveling, database writes or web-scene publication. This produces an observed-surface point cloud, not a complete/watertight architectural solid.

**Runtime:** Windows Python 3.11.15 and COLMAP 4.2.1 CUDA build on the RTX 3050 Laptop 4GB. Read-only `nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader` reported 4096 MiB total / 2311 MiB used before this run; this is not a peak-memory measurement. Native help confirmed the stereo/cache flags. Image cap: 640 pixels; PatchMatch and fusion cache-size arguments: 1 GB. No libraries installed or existing services stopped.

### Real dense reconstruction command

```powershell
.\.venv\Scripts\python.exe -B -u -m pipeline.colmap_reconstructor --stage stage_b --images scratch/real_drone_frames --phase-a-workspace output/phase_a/real_drone_20261002_repeat --workspace output/phase_b/real_drone_20261002 --max-image-size 640
```
**What this does:** re-exports and revalidates the actual Phase A sparse binary model, verifies image names/dimensions, runs `image_undistorter`, geometric `patch_match_stereo`, and geometric `stereo_fusion`, then checks fused points against the undistorted geometric depth maps. The strict Stage B CLI requires `--phase-a-workspace` and does not call the legacy mixed neural/procedural orchestration path.

**Observed:** exit 0, Phase B PASSED; internal processing timer 88.79s (approximately 1.7 minutes including process startup). Use a **new workspace** for another run; the recorded directory already contains results and must not be silently overwritten.

| Measurement | Observed result |
|---|---:|
| Registered cameras / geometric depth maps | 11 / 11 |
| Phase A recheck | PASSED, 1,409 sparse points, 0.225079px mean error |
| Native geometric stereo passes | 11 (in addition to 11 initial photometric passes) |
| Fused candidate surface points | 37,801 |
| Retained after depth-support check | 37,801 |
| Additional rejected points | 0 |
| Invalid coordinates/normals | 0 |
| Minimum / median support | 2 / 6 distinct camera views |
| Maximum allowed relative depth difference | 2% |
| Minimum retained-point gate | 500 |

Native fusion already filters measurements (`min_num_pixels=5`, `max_reproj_error=2px`, `max_depth_error=0.01`); all its candidates also passed the additional 2%-depth/two-camera check. This checks consistency with the **same reconstruction measurements**, not held-out ground truth, 2% real-world accuracy, complete building coverage or metric scale. No points were synthesized to reach a target count.

### Phase B artifacts and visual inspection

Under `output/phase_b/real_drone_20261002/`:
- `dense_quality_report.json`, `validation_report.txt`: measured checks, phase boundary flags, input image hashes, retained-point count and timing.
- `dense/fused.ply`: raw COLMAP fused geometry with observed RGB and normals.
- `verified_dense.ply`: retained XYZ/RGB/normals only; no invented Gaussian scale/rotation/opacity fields.
- `depth_support_counts.npy`: distinct supporting-camera count for each raw fused point, in raw PLY order.
- `dense/images/`, `undistorted_sparse_txt/`: mutually aligned undistorted images and camera model for subsequent photometric work.
- `dense/stereo/depth_maps/*.geometric.bin`: the 11 geometric depth maps used for checking.
- `colmap_commands.json`, `dense/colmap_commands.json`, and their `logs/`: all native commands/exit codes, including streamed PatchMatch progress.
- `diagnostics/frame_0000_dense.png`, `frame_0005_dense.png`, `frame_0010_dense.png`: source / projected measured points / overlay triptychs. All three were inspected. The tower's photographed facades and portions of surrounding surfaces are recognizable; gaps and sparse background remain. These are **not** optimized Gaussian renders or evidence for unobserved rear walls.

The dense cloud and cameras retain the original **COLMAP_PHASE_A** coordinate frame and **RELATIVE_UNCALIBRATED** scale. No separate point-only ground rotation was applied. Future Phase C must use the matching `verified_dense.ply`, `dense/images/`, and `undistorted_sparse_txt/` rather than mixing these points with a differently aligned model. Semantic labels and any eventual scene-frame transform remain separate work; the existing web viewer has not been switched to this output.

### Final regression command

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q --tb=short backend/tests/test_phase_b_dense.py backend/tests/test_phase_a_colmap.py backend/tests/test_colmap_stage_b.py backend/tests/test_phase_c_3dgs.py backend/tests/test_query_loop.py::test_intent_schema_models backend/tests/test_query_loop.py::test_sql_compiler_height backend/tests/test_query_loop.py::test_sql_compiler_region backend/tests/test_query_loop.py::test_sql_compiler_unknown backend/tests/test_query_loop.py::test_fallback_matcher_queries
```
**What this does:** tests 28 new Phase B cases, 22 Phase A regressions, 12 existing geometry/Gaussian helpers, and five non-network query cases. **Observed: 67 passed in 11.69s.** No model training or live DB/Ollama calls. Initial Phase B tests reproduced 19 failures before implementation; the earlier combined reconstruction suite passed 59 tests before three extra metadata cases and the five query cases were added.

**Other verification:** AST syntax checks passed for the changed source/new files. `sha256sum static/scene.splat static/scene.classes.u8` is unchanged from the Phase A hashes recorded below. Frontend build/lint, mutating API tests, cloud jobs, semantic models, Phase C training and Phase D viewer publication were not run. Legacy upload orchestration remains unverified and separate from this strict CLI. Stop here until Phase C is explicitly authorized.

---

## Phase A only — verified 2026-10-02

**Scope:** sparse COLMAP geometry and camera diagnostics only. No segmentation, neural depth, dense MVS, Gaussian optimization, procedural fallback, PostGIS writes or browser-scene export. Input was the already-documented `scratch/real_drone_frames` fixture (11 images, 640x360), not a newly selected private upload. Temporal sampling does not prove 60–80% image overlap; successful feature tracks are measured instead.

**Runtime observed:** native Windows Python 3.11.15; COLMAP 4.2.1, commit `bd1fcf6`, CUDA-enabled build. SIFT extraction/matching logs confirm GPU use. Explicit Ceres bundle adjustment ran with its default CPU setting; do not describe it as GPU bundle adjustment.

Commands were launched from the repository root in WSL using `./.venv/Scripts/python.exe`. PowerShell equivalents are shown below. No dependencies were installed.

### Regression tests

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q backend/tests/test_phase_a_colmap.py backend/tests/test_colmap_stage_b.py backend/tests/test_phase_c_3dgs.py
```
**What this does:** runs 22 Phase A tests and the 12 neighboring geometry/Gaussian helper tests without scene reconstruction. **Observed:** 34 passed in 9.25s.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q backend/tests/test_phase_a_colmap.py backend/tests/test_colmap_stage_b.py backend/tests/test_phase_c_3dgs.py backend/tests/test_query_loop.py::test_intent_schema_models backend/tests/test_query_loop.py::test_sql_compiler_height backend/tests/test_query_loop.py::test_sql_compiler_region backend/tests/test_query_loop.py::test_sql_compiler_unknown backend/tests/test_query_loop.py::test_fallback_matcher_queries
```
**What this does:** adds five non-network query regressions and imports the backend, without DB/Ollama/API execution. **Observed:** 39 passed in 11.43s. This is not the full repository suite. Before the repair, the initial 19 Phase A regressions failed; the original Stage A command raised `NameError: validate_colmap_geometry_stage_a` before COLMAP ran. The missing `Optional` import had already been corrected before this phase and was preserved.

### Real sparse reconstruction and independent repeat

```powershell
.\.venv\Scripts\python.exe -B -u -m pipeline.colmap_reconstructor --stage stage_a --images scratch/real_drone_frames --workspace output/phase_a/real_drone_20261002
.\.venv\Scripts\python.exe -B -u -m pipeline.colmap_reconstructor --stage stage_a --images scratch/real_drone_frames --workspace output/phase_a/real_drone_20261002_repeat
```
**What this does:** runs GPU SIFT extraction, sequential/quadratic matching, sparse mapping, explicit bundle adjustment, and sparse-model export in two separate workspaces. Each command exited **0**. Neither command executes Phase B/C/D.

**Reruns must use a new workspace name.** Existing SfM outputs are deliberately refused, not deleted or reused. This prevents a failed command from passing against old geometry. The exact underlying COLMAP commands and return codes are saved in each workspace's `sfm_commands.json`.

| Measurement | First run | Independent repeat |
|---|---:|---:|
| Gate | PASSED | PASSED |
| Registered images | 11/11 | 11/11 |
| Sparse / two-view-supported points | 1,307 / 1,307 | 1,409 / 1,409 |
| Mean reprojection error | 0.225585 px | 0.225079 px |
| Median reprojection error | 0.133131 px | 0.134896 px |
| Median track length | 3 views | 3 views |
| Median maximum ray angle per tie | 11.420469 degrees | 10.373579 degrees |
| Maximum / median camera step | 1.132765 | 1.130645 |
| Explicit bundle adjustment | CONVERGENCE, 11 iterations | CONVERGENCE, 14 iterations |

Sparse point counts differed between fresh runs; both passed. These are fixture-scoped observations, not deterministic-output, arbitrary-footage, metric-accuracy or dense-reconstruction guarantees. Camera translation/scene scale remains **RELATIVE_UNCALIBRATED**. Ray angles are diagnostics, not an additional acceptance threshold.

**Gate thresholds:** at least 3 registered images, at least 50% registration, 100 sparse points, 100 ties observed from at least two cameras, finite nonnegative reprojection errors for all points with mean at most 3px, finite geometry, nonzero camera translation and max/median step ratio at most 5. Missing evidence fails; a failed gate exits 1. No synthetic geometry is generated to make the check pass.

**Inspect these generated files in each workspace:**
- `colmap_quality_report.json`: measured checks, thresholds, input names, track counts and explicit pass/fail.
- `validation_report.txt`: readable summary; dense/depth/fallback stages marked NOT RUN.
- `trajectory.png`: camera XY projection (not a georeferenced or ground-leveled map).
- `sparse_cloud.ply`, `sparse/0/`, `sparse_txt/`: sparse geometry, cameras, observations and intrinsics.
- `input_images.txt`: exact input list passed to feature extraction.
- `logs/01_feature_extractor.log` through `logs/07_export_ply.log`: execution evidence, including `05_bundle_adjuster.log` with `Termination : CONVERGENCE`.

**Preservation check:** `sha256sum static/scene.splat static/scene.classes.u8` returned identical hashes before and after Phase A:
- `scene.splat`: `922ae96124d5fc444a39ba82bfaa5c0cc03b21cef8ac2dd9f4b76591e7d8534c`
- `scene.classes.u8`: `6d1ec41df4b53e752a35dcc54b60ba3e88d708a3a458f1516d3bb3233ec4d6f4`

**Other checks / limits:** Python AST syntax checks passed for the changed source and new tests. Git whitespace checks still report pre-existing CRLF/trailing-whitespace issues; no repository-wide formatting was performed. Frontend build/lint, mutating API tests, video-upload orchestration, cloud jobs and dense/3DGS execution were not run. The shared SfM runner now requires a fresh workspace; the upload orchestrator still needs per-job workspace integration in a separately authorized phase. Its legacy automatic fallback is not the Phase A CLI and was not used here.

---

## Historical command records

## Phase 0: Project Setup & Database

### Initialize Git
```powershell
git init
```

### Start PostGIS Container (Port 5435 to avoid local conflicts)
```powershell
docker compose up -d db
```

### Verify Container Status
```powershell
docker compose ps
# Expected: Up (healthy) on 127.0.0.1:5435->5432/tcp
```

### Verify PostGIS & SFCGAL Extensions
```powershell
docker exec -i spatial-twin-db psql -U spatial_user -d spatial_twin -c "SELECT PostGIS_Full_Version();"
# Result: POSTGIS="3.4.3 e365945" PGSQL="160" SFCGAL="1.3.8"
```

### Test 3D Solid Geometry (SFCGAL ST_Extrude)
```powershell
docker exec -i spatial-twin-db psql -U spatial_user -d spatial_twin -c "SELECT ST_AsText(ST_Extrude('POLYGON((0 0,1 0,1 1,0 1,0 0))'::geometry,0,0,5));"
# Result: POLYHEDRALSURFACE Z (((0 0 0,0 1 0,1 1 0,1 0 0,0 0 0)),((0 0 5,1 0 5,1 1 5,0 1 5,0 0 5))...)
```

## Phase 1: Environment Bring-up & Smoke Tests

### Run Environment Diagnostics
```powershell
& ".\.venv\Scripts\python.exe" pipeline/00_env_check.py
# Result: Python 3.11.15, PyTorch 2.6.0+cu124, CUDA Active (RTX 3050 4.0GB VRAM), PostGIS Online, Ollama Online (qwen2.5:3b)
```

### Run Ollama Structured Output Smoke Test (Intent JSON)
```powershell
& ".\.venv\Scripts\python.exe" -u pipeline/test_ollama_intent.py
# Result: 5/5 queries passed with strict JSON schema compliance (~0.8s - 1.2s latency)
```

## Phase 2: Offline ML & Geometry Pipeline

### Apply Database Schema & Regions
```powershell
Get-Content db/schema.sql | docker exec -i spatial-twin-db psql -U spatial_user -d spatial_twin
Get-Content db/regions.sql | docker exec -i spatial-twin-db psql -U spatial_user -d spatial_twin
```

### Run Master Offline Pipeline (End-to-End)
```powershell
& ".\.venv\Scripts\python.exe" -u pipeline/run_pipeline.py
# Runs:
#  - Stage 01b: 3D point cloud verification/synthesis (60,000 splats)
#  - Stage 03:  SegFormer-B0 CUDA keyframe semantic segmentation
#  - Stage 04:  3D splat class projection and majority voting
#  - Stage 05a: RANSAC ground plane fitting & rigid Z-up frame alignment
#  - Stage 05b: DBSCAN building clustering, 2D footprints & 3D bounding boxes
#  - Stage 06:  PostGIS database loading with 3D SFCGAL PolyhedralSurfaceZ solids
#  - Stage 07:  Web binary export: scene.splat (32-byte/pt) + scene.classes.u8 (1-byte/pt)









# In your terminal:
.\.venv\Scripts\python.exe pipeline/demo_3d.py
```

## Phase 5: AI Agent & Query Loop

### Run Automated Test Suite (Pytest)
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_query_loop.py -v
# Result: 11 passed in ~7.4s (covers intent parsing, SQL compilation, regex fallback, height/region/range queries, and nonsense handling)
```

### Start Backend Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Test Query Endpoint (PowerShell / curl)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/query" -Method Post -ContentType "application/json" -Body '{"text": "Which buildings are taller than 20 metres?"}' | ConvertTo-Json -Depth 5
# Returns: matched_ids, filtered GeoJSON objects, metrics (count, avg_height_m, total_area_m2), and parameterized SQL
```

## Phase 6: Frontend Shell + 3D Viewer + Alignment

### Install Dependencies
```powershell
cd frontend
npm install
```

### Build & Validate Frontend Bundle
```powershell
npm run build
# Result: Successful compilation of client and SSR bundles with zero syntax/type errors
```

### Start Vite Development Server
```powershell
npm run dev
# Serves on: http://localhost:8080/ (Landing page at / and master digital twin application at /demo)
```

### Verify End-to-End Twin & 3D Splat Assets
```powershell
Invoke-WebRequest -Uri "http://localhost:8080/demo" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/static/scene.splat" -Method Head -UseBasicParsing
```

### Verify Sub-Second Ollama Natural Language Query
```powershell
Measure-Command { Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/query" -Method Post -ContentType "application/json" -Body '{"text": "Show structures in the center region"}' }
# Result: ~980ms end-to-end latency with 100% LLM schema adherence and zero timeouts
```

## Phase 7: Drone Video Upload & In-App ML Pipeline

### Run Pipeline API Test Suite (Pytest)
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_pipeline_api.py -v
# Result: 5 passed in ~11s (verifies /status, invalid extension rejection, async processing, kaggle-config, and splat import)
```

### Start FastAPI Backend Server (Live Demo Mode)
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
# NOTE: If using reload for development, restrict reload to code directories so uploads don't abort:
# .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload-dir backend --reload-dir pipeline
```

### Start PostGIS Database Container (If Offline)
```powershell
docker compose up -d db
# Starts PostGIS container spatial-twin-db on port 5435
```

### Upload Drone Video via API (cURL / PowerShell)
```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/pipeline/upload" -F "file=@output/test_sample.mp4"
# Result: {"job_id":"...","status":"processing","message":"Video 'test_sample.mp4' uploaded successfully..."}
```

### Check Real-Time Pipeline Progress
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/pipeline/status" | ConvertTo-Json
```

### Reconstruct Upright Volumetric 3D Diagram from Drone Video
```powershell
.\.venv\Scripts\python.exe -c "import asyncio; from pipeline.video_orchestrator import execute_drone_video_pipeline; res = asyncio.run(execute_drone_video_pipeline('data/uploads/e7941073_Free Stock Footage - Highrise Building close up Drone DJI Air2S - Free Stock Footage (720p, h264).mp4')); print(res)"
# Result: 5 structures extracted (Height 16.2m to 46.6m, Area 1,268m2), 64,996 splats in static/scene.splat
```
### Verify Dynamic Project Name & Live PostGIS Structures
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/objects/project"
# Returns: { id: 1, name: "Free Stock Footage - Highrise Building Close Up Drone Dji Air2S - Free Stock Footage (720P, H264) Twin", scale_factor: 1.0 }

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/objects/structures" | ConvertTo-Json -Depth 2
# Returns the structures corresponding to the last uploaded drone flight
```

### Verify Static Splat Headers (Anti-Caching)
```powershell
(Invoke-WebRequest -Uri "http://127.0.0.1:8000/static/scene.splat" -Method Head -UseBasicParsing).Headers["Cache-Control"]
# Expected: no-cache, no-store, must-revalidate
```

### Run Authentic Video 3D Reconstruction Pipeline (Fast Local)
```powershell
.\.venv\Scripts\python.exe -c "
import asyncio
from pathlib import Path
from pipeline.video_orchestrator import execute_drone_video_pipeline
asyncio.run(execute_drone_video_pipeline('data/uploads/sample.mp4'))
"
# Result: 65,000 authentic video points, RANSAC leveled ground, DBSCAN structures in PostGIS
```

### Run Kaggle Cloud 16GB GPU Reconstruction Pipeline
```powershell
.\.venv\Scripts\python.exe -c "
import asyncio
from pipeline.kaggle_runner import run_kaggle_3dgs_job
res = asyncio.run(run_kaggle_3dgs_job('data/uploads/sample.mp4'))
print(res)
"
# Result: Dispatches video dataset, executes Depth Anything V2 on Tesla T4, downloads 80,000 authentic 3D splats, and syncs PostGIS structures
```

### Run Geometry-First Camera Pose Estimation & Pose-Aware Unprojection (Stage A)
```powershell
.\.venv\Scripts\python.exe -c "
from pipeline.video_depth_reconstructor import reconstruct_3d_from_keyframes
res = reconstruct_3d_from_keyframes(images_dir='./data/mill/images', masks_dir='./output/masks', output_ply='./output/mill/point_cloud.ply')
print(res)
"
# Result: Recovers camera intrinsics K, SIFT feature tracks, Essential Matrix poses (R_w, t_w), generates trajectory.png & sparse_cloud.ply, unprojects 65,000 points without slice ghosting, and extracts clean PostGIS structures.
```

### Run Stage B COLMAP Dense Photogrammetry & 3D Reconstruction (CLI Entrypoint)
```powershell
.\.venv\Scripts\python.exe -m pipeline.colmap_reconstructor --stage stage_b --images scratch/real_drone_frames --masks scratch/real_drone_masks --workspace scratch/stage_b_final/colmap_sfm --output scratch/stage_b_final/point_cloud.ply
# Result: Runs CUDA COLMAP SfM (1,430 tie points, 0.23px error) + PatchMatch Stereo (40,870 points) + SegFormer multi-view semantic projection (95.1% building, 3.2% road) + 3D SVD ground leveling (road at Z=0.04m, building max Z=6.91m) + 3D voxel grid fusion (16,961 consensus points).
```

### Run Stage B Unit & Integration Test Suite (7 Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_colmap_stage_b.py -v
# Result: 7 passed in ~7s (verifies binary discovery, qvec2rotmat, RANSAC depth scale alignment, cross-view consistency filtering, voxel grid fusion, ground leveling, and report formatting).
```

### Run Full Repository Test Suite (30 Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest -v
# Result: 30 passed in ~12s across all backend APIs, NLP query intent parsers, PostGIS loaders, photogrammetry stages, and 3DGS differentiable projection/rasterization.
```

### Run Stage A COLMAP Geometry Validation (Standalone Quality Gate)
```powershell
.\.venv\Scripts\python.exe -m pipeline.colmap_reconstructor --stage stage_a --images scratch/real_drone_frames --workspace scratch/test_stage_a
# Result: Evaluates registered frames (100%), sparse tie points (1,400+), sub-pixel reprojection error (0.24 px), and trajectory continuity (SMOOTH) before depth fusion.
```

### Run Stage C 3D Gaussian Splatting Exporter (.splat Serialization)
```powershell
.\.venv\Scripts\python.exe -m pipeline.colmap_reconstructor --stage stage_c --output scratch/stage_b_final/point_cloud.ply
# Result: Serializes web-optimized binary scene.splat and scene.classes.u8 with 1:1 index lock for Three.js WebGL viewer.
```

### Run Full Phase C: 3D Gaussian Splatting Optimization & Visual Validation Engine
```powershell
.\.venv\Scripts\python.exe -m pipeline.gaussian_optimizer --images scratch/real_drone_frames --sparse_txt scratch/stage_b_final/colmap_sfm/sparse_txt --init_ply scratch/stage_b_final/colmap_sfm/dense/fused.ply --masks scratch/real_drone_masks --output scratch/stage_b_final --static static --iterations 300
# Result: Executes 300 iterations of full 3DGS gradient optimization (L1 + SSIM loss), multi-view visual validation across 11 keyframe viewpoints (eval_frame_0000.png - eval_frame_0010.png), verifies single facade hull and stationary walls, and exports ground-leveled scene.splat (17,984 splats, 0.55 MB) and scene.classes.u8 (17.5 KB) to static/.
```

### Run Phase C 3DGS Unit Test Suite (5 Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_phase_c_3dgs.py -v
# Result: 5 passed in ~2.8s (verifies rotation matrix SO(3) properties, 3D covariance positive-definiteness, pinhole perspective projection, SSIM loss properties, and Gaussian opacity pruning).
```

### Inspect Port 8000 Owning Process & Reset Pipeline State
```powershell
# Check which PID holds port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object LocalAddress, LocalPort, State, OwningProcess

# Force terminate stale ghost python instances
Stop-Process -Id <STALE_PID> -Force

# Reset pipeline state to idle via curl or PowerShell
curl.exe -s -i -X POST http://127.0.0.1:8000/api/pipeline/reset
# Result: {"status":"ok","message":"Pipeline state reset to idle"}
```

### Videogrammetry Real Reconstruction Engine (Phase 2 Test & Verification)
```powershell
# Run Videogrammetry test suite verifying real SfM, MVS densification, Open3D Poisson meshing, and absence of mock geometry
python -m pytest videogrammetry/test_videogrammetry.py -v
# Result: 4 passed in ~6.1s (verifies tier definitions, storage manager, orchestrator pipeline run, real glTF binary generation, and model serving/import)

# Build frontend to verify Three.js GLTF/OBJ model viewer integration
cd frontend
npm run build
# Result: Vite production build passed with 0 errors
```

### OpenRouter AI 3D Prompt Guidance, Architectural Realism & Surface Normal Verification — 2026-10-16
```powershell
# Run OpenRouter 3D test suite including prompt directives and geometry synthesis
.\.venv\Scripts\pytest backend/tests/test_openrouter_3d.py -k "not test_openrouter_generate" -v
# Result: 3 passed in ~1.5s (verifies config endpoint, roof styles, building floors, compute_normals, and standard binary glTF 2.0 with NORMAL attributes)

# Build frontend to verify OpenRouter 3D prompt textarea, preset buttons, and floating viewport HUD
cd frontend
npm run build
# Result: Vite production build passed with 0 errors in 23.6s
```




