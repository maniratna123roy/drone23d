# Videogrammetry Sidecar Approach — Architecture & Implementation

> **Subsystem**: Continuous Drone-Video-to-3D Reconstruction Sidecar  
> **Reference Model**: Skyebrowse Public Architectural Principles  
> **Status**: Fully Implemented & Integrated as a Dedicated Parallel Approach  
> **Integration Mode**: Non-Invasive Sidecar with Clean Gateway Route & Dedicated Frontend Dashboard  

---

## 1. Executive Summary

The **Videogrammetry Approach** is a parallel 3D reconstruction system built directly into this project to run alongside the existing **3D Gaussian Splatting** system.

Where the host system is focused on **photorealistic neural view synthesis (Gaussian Splatting)** coupled with an Ollama NLP translator and PostGIS intelligence layer, the Videogrammetry approach is modeled after **Skyebrowse's continuous videogrammetry workflow**:
1. **Input**: A single, continuous drone flight video pass (MP4 / MOV) plus optional companion DJI `.SRT` or GPS telemetry.
2. **Method**: Structure-from-Motion (SfM) + Multi-View Stereo (MVS) + Poisson Surface Meshing + Orthomosaic rendering.
3. **Outputs**: Native CAD and GIS deliverables — standard textured polygon meshes (`.glb`, `.obj`), metric point clouds (`.laz`), Cloud-Optimized GeoTIFFs (`.tif`), and Digital Surface Models (DSM).
4. **Reliability**: An **Automated AI Quality Gate** featuring an automated 3-attempt redo ladder.

---

## 2. Approach Comparison: Gaussian Splatting vs Videogrammetry

| Dimension | Approach A: 3D Gaussian Splatting (Current Host) | Approach B: Videogrammetry Sidecar (Skyebrowse Model) |
|---|---|---|
| **Primary Primitive** | 3D ellipsoidal Gaussian splats (mean, covariance, opacity, spherical harmonics) | Triangular polygon mesh (vertices, faces, texture atlas) + metric point clouds (LAZ) |
| **Mathematical Core** | Radiance field gradient optimization via `gsplat` / tile rasterizer | Sequential SfM (COLMAP/GLOMAP) + Multi-View Stereo (MVS) + Surface Poisson Meshing |
| **Input Data** | Hundreds of discrete multi-view photos with calibrated camera poses | Single continuous video recording + optional companion DJI `.SRT` GPS track |
| **Ground Control Points (GCPs)** | Not required for local coordinates | None required; uses per-frame GPS prior with Umeyama similarity alignment |
| **Moving Objects** | Produce floater artifacts unless hand-cleaned | Dynamic-object instance masking eliminates cars/pedestrians before matching |
| **CAD / GIS Interoperability** | Low (splats lack discrete topology; requires proxy geometry) | Native (opens directly in Blender, Rhino, AutoCAD, ArcGIS, QGIS) |
| **Quality Control** | Manual inspection of training loss curves (PSNR / SSIM) | Automated AI Quality Gate with multi-stage retry ladder |
| **Browser Rendering** | Custom WebGL/WebGPU splat sorting and Gaussian rasterizer | Standard Three.js PBR mesh rendering (zero custom shaders needed) |
| **Target Use Cases** | Immersive digital twins, photoreal virtual tours, natural-language spatial edits | Volumetric surveys, boundary measurements, GIS mapping, disaster site CAD |

---

## 3. Non-Invasive Sidecar Principles

The implementation strictly satisfies the isolation and zero-regression criteria laid out in `Videogrammetry Sidecar - System Architecture.md`:
1. **Zero Host Edits**: The host project's database schemas, Gaussian Splatting pipelines, and core APIs remain completely untouched.
2. **Dedicated Sidecar Package**: All videogrammetry logic resides in the dedicated `videogrammetry/` folder:
   - `videogrammetry/models.py`: Schemas for captures, stages, artifacts, and quality reports.
   - `videogrammetry/tiers.py`: Quality and resolution tier definitions.
   - `videogrammetry/storage.py`: Storage manager with `raw/`, `frames/`, `work/`, `out/` isolation.
   - `videogrammetry/stages/`: Individual implementations for Stages 0 through 8.
   - `videogrammetry/orchestrator.py`: State machine driving stages and retry ladders.
   - `videogrammetry/api.py`: FastAPI server serving the Capture API contract and artifacts.
   - `videogrammetry/run_sidecar.py`: Standalone runner on port `8001`.
3. **Storage Isolation**: Intermediate and published files are placed under `output/videogrammetry/captures/{capture_id}/`.
4. **Dual Running Modes**:
   - **Standalone Service**: Can be run independently via `python videogrammetry/run_sidecar.py` on port `8001`.
   - **Frontend Browser Emulation**: If the backend sidecar is offline, the frontend provides instant progressive simulation with realistic stage transitions and metrics.

---

## 4. Pipeline Stages (0 through 8)

### Stage 0: Validate & Probe (`stage0_probe.py`)
- **Probing**: Checks video stream presence, codec, resolution, fps, frame count, and duration.
- **Telemetry Extraction**: Scans for companion DJI `.SRT` subtitle tracks or uploaded GPS JSON files. Parses per-second/frame coordinates (`lat`, `lon`, `alt_m`).
- **Input Validation**: Issues warnings if the clip is shorter than 10 seconds or resolution is below 720p.

### Stage 1: Frame Extraction & Selection (`stage1_frames.py`)
- **Sharpness Scoring**: Calculates the variance of the Laplacian across candidate frames; discards blurriest frames.
- **Parallax Keyframe Selection**: Uses ORB feature matching to measure median keypoint pixel displacement between frames. Only retains frames when displacement reaches 3–5% of image width.
- **Budget Control**: Caps the keyframe count to the active tier's frame budget (200, 400, 700, or 1500).

### Stage 2: Dynamic-Object Masking (`stage2_masking.py`)
- **Isolation**: In Premium and Premium Advanced tiers (or during Retry Ladder attempts), applies background motion segmentation to identify moving cars, pedestrians, and dynamic foliage.
- **Mask Generation**: Writes binary PNG masks to `frames/masks/` so dynamic objects do not produce false correspondences during feature matching.

### Stage 3: Pose Estimation & SfM (`stage3_sfm.py`)
- **Sequential Matching**: Exploits the sequential temporal nature of continuous video by matching across a sliding window of 10–20 neighbors plus loop closures.
- **GPS Prior**: Applies a robust Umeyama similarity transform to align camera centers to a local East-North-Up (ENU) metric frame.
- **Output**: Camera trajectories (`camera_poses.json`) and sparse 3D point cloud.

### Stage 4: Dense Reconstruction (`stage4_dense.py`)
- **MVS Fusion**: Multi-View Stereo PatchMatch depth map fusion with geometric consistency filtering.
- **Scene Tiling**: Partitions large scenes into manageable spatial bounding boxes to bound memory requirements.
- **Output**: Dense colored 3D point cloud.

### Stage 5: Surface Meshing & Texturing (`stage5_mesh.py`)
- **Surface Extraction**: Delaunay / Poisson surface reconstruction.
- **Decimation**: Simplifies the mesh to match the tier triangle budget (50k to 2M triangles).
- **Texturing**: Generates texture atlases with view selection and seam leveling.
- **Deliverables**: Valid Wavefront `.obj` and `.mtl` models.

### Stage 6: Georeferenced Products (`stage6_georef.py`)
- **Orthomosaic**: Renders a top-down orthographic view at the target Ground Sample Distance (GSD, e.g. 2.5 cm/px) into `orthomosaic.png` and GeoTIFF format.
- **Digital Surface Model (DSM)**: Rasterizes point cloud heights into a 2D elevation grid.
- **Point Cloud**: Writes georeferenced metric point cloud (`point_cloud.laz`).

### Stage 7: AI Quality Gate (`stage7_quality_gate.py`)
Evaluates the reconstruction against photogrammetric thresholds:
- Registered frames ratio $\ge 0.85$
- Mean reprojection error $\le 1.0\text{ px}$
- Mesh hole area ratio $< 2.0\%$
- Held-out view check $\text{SSIM} \ge 0.70$
- Outlier geometry ratio $< 1.0\%$

**Automated Retry Ladder (up to 3 attempts):**
1. *Attempt 1 Retry*: Increase frame budget by 25% and widen matching window.
2. *Attempt 2 Retry*: Enable dynamic-object instance masking.
3. *Attempt 3 Retry*: Upgrade to high-resolution feature extraction with sub-pixel refinement.
4. *Degraded Fallback*: If metrics remain below threshold after max retries, the model is shipped flagged as `DEGRADED` with failing metrics transparently displayed.

### Stage 8: Export & Publish (`stage8_export.py`)
- **Standard Binary glTF**: Builds a self-contained, valid binary `.glb` model with PBR material definitions for instant WebGL loading.
- **Checksums**: Calculates SHA-256 hashes for all published artifacts.
- **Audit Manifest**: Writes `manifest.json` recording inputs, tier parameters, CRS, quality report, and accuracy statements.

---

## 5. Quality Tiers

| Tier | Frame Budget | Resolution | Dynamic Masks | QA Retries | Triangle Budget | Intended Output |
|---|---|---|---|---|---|---|
| **Lite** | ~200 | 1080p | Off | 0 | 50,000 | Quick 3D preview, coarse mesh |
| **Standard** | ~400 | 4K | Off | 1 | 250,000 | Operational documentation, textured mesh |
| **Premium** | ~700 | 4K to 8K | On | 2 | 750,000 | Measurement-grade mesh, point cloud, ortho |
| **Premium Advanced** | up to 1,500 | 8K (tiled) | On | 3 | 2,000,000 | Sub-centimeter accuracy, auto redo loop |

---

## 6. Frontend Integration

A dedicated route and interface has been added to the frontend:
- **Route**: Accessible at `/videogrammetry`.
- **Navbar Integration**: A prominent **"Videogrammetry Approach"** button with live pulse indicator sits in the navigation bar.
- **Key UI Surfaces**:
  1. **Header & Approach Switcher**: Easily jump back to the Gaussian Splatting demo (`/demo`) or Home (`/`).
  2. **Architectural Comparison Modal**: Click *"Compare Approaches"* for a point-by-point technical breakdown.
  3. **Tier Selector**: Interactive cards configuring frame budgets, resolution, masks, and redo limits.
  4. **Video & Telemetry Uploader**: Upload continuous drone footage, load companion DJI `.SRT` files, or click *"Load Verified Drone Sample Pass"* for instant one-click testing.
  5. **State Machine Pipeline Tracker**: 8 visual step cards with status badges and duration metrics.
  6. **AI Quality Gate Report Card**: Interactive meters for Registration Ratio, Reprojection Error, SSIM, and Hole Area with AI Verdict badge (`PASS` / `RETRY` / `DEGRADED`).
  7. **Interactive 3D Mesh Viewer**: Three.js viewport with OrbitControls, Solid/Wireframe toggle, lighting, and dimension tags for Mill-19 structures.
  8. **Orthomosaic & DSM Viewer**: Top-down 2D map view with layer toggles (Orthomosaic RGB vs DSM Elevation), zoom controls, and scale bar.
  9. **Published Artifacts Download Hub**: Direct download buttons for `scene.glb`, `mesh.obj`, `orthomosaic.png`, `point_cloud.laz`, and `manifest.json`.

---

## 7. How to Run & Verify

### Running the Backend Sidecar Service
To start the independent Videogrammetry API on port `8001`:
```powershell
.\.venv\Scripts\python.exe videogrammetry\run_sidecar.py
```
*API Swagger Documentation will be live at: `http://127.0.0.1:8001/docs`.*

### Running the Frontend
To start the frontend application:
```powershell
cd frontend
npm run dev
```
Open `http://localhost:5173/` and click the **"VIDEOGRAMMETRY APPROACH"** button in the header (or navigate directly to `http://localhost:5173/videogrammetry`).

### Running the Automated Test Suite
To verify all 8 stages, quality gate, tier definitions, and artifact generation:
```powershell
.\.venv\Scripts\pytest.exe videogrammetry\test_videogrammetry.py
```
*Expected result: 3 passed tests (all assertions green).*
