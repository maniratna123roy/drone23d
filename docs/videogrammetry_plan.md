# Real Videogrammetry & Drone-to-3D Implementation Plan

> **Goal**: Replace mock/synthetic 3D scene generation with real, functional video-to-3D reconstruction from actual drone footage — both locally and via cloud GPU (Google Colab).  
> **Target Deliverables**: Real textured 3D mesh (`scene.glb`, `mesh.obj`), real metric point clouds (`point_cloud.ply`, `point_cloud.laz`), and top-down orthomosaics (`orthomosaic.png`).

---

## 1. Root Cause Analysis: Why Was It Displaying 3 Mock Buildings?

In accordance with **Project Rule 10 (Honesty Rule)**, here is the exact reason why the previous videogrammetry approach showed 3 synthetic buildings:

1. **Frontend Viewer Hardcoding (`frontend/src/components/videogrammetry/Viewer3DMesh.tsx` lines 97–133)**:
   - The Three.js viewer had 3 procedural `THREE.BoxGeometry` boxes hardcoded directly into the render loop:
     - Building 1: `Mill-19 North Wing` (`BoxGeometry(14, 11.5, 20)`)
     - Building 2: `Control Tower & Offices` (`BoxGeometry(11, 16.5, 13)`)
     - Building 3: `Logistics Depot` (`BoxGeometry(22, 8, 9)`)
   - It did **not** use Three.js `GLTFLoader` or `OBJLoader` to fetch the actual reconstructed file from the backend API.
2. **Backend Stage 5 Hardcoding (`videogrammetry/stages/stage5_mesh.py` lines 56–89)**:
   - When generating `mesh.obj`, `Stage5Mesh` wrote hardcoded box coordinates for those exact 3 buildings instead of performing surface reconstruction on real point clouds.
3. **Backend Stage 3 & 4 Synthetic Data (`stage3_sfm.py` lines 72–110, `stage4_dense.py`)**:
   - `stage3_sfm.py` detected SIFT features, but then assigned camera positions along an idealized mathematical circle:
     `cam_x = orbit_radius * math.cos(t)`
   - It generated synthetic points on a fixed radial grid instead of triangulating real 3D points.

---

## 2. Real Architecture: Two Complementary Reconstruction Paths

Drone video-to-3D requires two complementary execution modes based on hardware:

```
                                  [Drone Flight Video (MP4/MOV)]
                                                 │
                   ┌─────────────────────────────┴─────────────────────────────┐
                   ▼                                                           ▼
       [PATH A: Local GPU/CPU Pipeline]                            [PATH B: Google Colab Cloud Pipeline]
       (For immediate testing on RTX 3050 4GB)                     (For high-fidelity training on T4/A100)
                   │                                                           │
        • Real Keyframe Extraction (OpenCV)                         • Keyframe Extraction (FFmpeg)
        • Metric Depth AI (Depth Anything V2)                       • Sequential COLMAP SfM (Exact Camera Poses)
        • Multi-view Back-Projection                                • 3D Gaussian Splatting (gsplat / 7000 steps)
        • Open3D Poisson Surface Reconstruction                     • OpenMVS / Poisson Textured Meshing
                   │                                                           │
                   ▼                                                           ▼
         scene.glb + point_cloud.ply                                 scene.splat + scene.glb + point_cloud.ply
                   │                                                           │
                   └─────────────────────────────┬─────────────────────────────┘
                                                 ▼
                          [Frontend Three.js GLTFLoader Viewport]
                          (Renders real geometry, textures, and metrics)
```

### Real-World Analogy (Beginner Mode)
> **Analogy**: Imagine taking a drone flight around a statue.  
> - **Path A (Local Fast Sculptor)**: Takes photo snapshots from the flight, uses an AI depth sensor to estimate distances from the camera, and glues the surfaces together into a 3D clay model in 2–3 minutes.  
> - **Path B (Colab Master Sculptor)**: Takes all photos into a high-powered cloud studio, matches millions of microscopic visual landmarks across the photos, calculates the camera's trajectory down to the millimeter, and trains 1.5 million microscopic colored droplets (Gaussian Splats) or a dense mesh.

---

## 3. Training Datasets & Links

For training or testing real drone 3D reconstruction, use these standard drone benchmark datasets:

| Dataset | Description | Drone Pattern | Download Link |
|---|---|---|---|
| **Mill-19 (Mega-NeRF)** | Industrial site in Pittsburgh, PA (Building & Rubble scenes). ~400–800 aerial drone images with calibrated poses. | Orbital + Grid drone passes | [Mega-NeRF GitHub / CMU](https://cmusatyalab.github.io/mega-nerf/) |
| **Tanks and Temples** | High-precision photogrammetry benchmark (outdoor & architectural scenes like Family, Francis, Horse). | Multi-angle continuous orbit | [Tanks and Temples Benchmark](https://www.tanksandtemples.org/download/) |
| **OpenDroneMap (ODM) Sample Data** | Real public drone mapping datasets (Bellus, Brighton Beach, Park, Building). Includes aerial imagery + GPS geotags. | Aerial nadir / oblique grid | [ODM Sample Datasets Repository](https://github.com/OpenDroneMap/odm_data) |
| **Custom Drone Footage** | Your own continuous drone video pass (MP4 or MOV). | Orbit around a building or 70% overlap grid at 30–50 m altitude | User uploaded |

---

## 4. Google Colab Training Workflow & Script

When you have a drone video and want high-fidelity reconstruction:

### How to Run on Google Colab:
1. Open [Google Colab](https://colab.research.google.com).
2. Click **File > New notebook** (or upload the script below).
3. Select **Runtime > Change runtime type > T4 GPU** (free tier has 15 GB VRAM).
4. Run the cells to:
   - Mount your Google Drive.
   - Install COLMAP and 3D Gaussian Splatting (`gsplat`).
   - Upload or download your drone video / dataset.
   - Extract keyframes and run camera pose estimation.
   - Optimize the 3D model and export `scene.splat`, `point_cloud.ply`, and `scene.glb`.
5. The outputs are automatically saved to your Google Drive in `Google Drive/SpatialTwin_Outputs/`.

---

## 5. Phased Implementation Roadmap

Following **Project Rule 2 ("One phase at a time: Finish, verify, report, then STOP and wait for user's explicit confirmation to proceed")**:

### Phase 1: Real Frontend Viewer & API Model Serving (P0)
- **Goal**: Make `Viewer3DMesh.tsx` load **real** 3D model files via Three.js `GLTFLoader` and `OBJLoader` instead of rendering hardcoded boxes.
- **Changes**:
  - Update `Viewer3DMesh.tsx` with dynamic model loading, loading spinner, bounding box auto-centering, and error handling.
  - Update `videogrammetry/api.py` to ensure `/v1/captures/{id}/artifacts/scene.glb` serves proper MIME types with CORS.
- **Verification**: Load a real sample `.glb` model into the viewer; verify orbit controls and dimensions reflect real model geometry.

### Phase 2: Real Local Reconstruction Engine (P0)
- **Goal**: Replace synthetic stages in `videogrammetry/stages/` with real computer vision and surface reconstruction.
- **Changes**:
  - `stage1_frames.py`: Real keyframe extraction with Laplacian sharpness filtering and perceptual hash displacement.
  - `stage3_sfm.py`: Sequential feature matching using OpenCV SIFT + camera relative pose estimation ($R, t$ via Essential Matrix decomposition).
  - `stage4_dense.py`: Monocular metric depth estimation using `Depth Anything V2` (already installed and working in the host pipeline) to back-project 2D video pixels into a 3D point cloud with real RGB colors.
  - `stage5_mesh.py`: Real Open3D Poisson Surface Reconstruction (`create_from_point_cloud_poisson`) + mesh simplification to generate real polygon mesh files (`mesh.obj`, `scene.glb`).
  - `stage8_export.py`: Pack real glTF binary with vertex colors and textures.
- **Verification**: Run `python videogrammetry/run_sidecar.py`, trigger reconstruction with a test video, verify generated `scene.glb` contains actual reconstructed vertices and surfaces from the video frames.

### Phase 3: Google Colab Training Script & Pipeline Notebook (P0)
- **Goal**: Provide a complete, self-contained Google Colab notebook (`pipeline/videogrammetry_colab_training.ipynb`) and standalone training script.
- **Changes**:
  - Google Drive mounting and automated folder structure.
  - Video-to-keyframes automated conversion with FFmpeg.
  - COLMAP feature extraction & sequential bundle adjustment on GPU.
  - 3D Gaussian Splatting training via `gsplat` (7,000 steps).
  - Point cloud and textured mesh conversion.
  - Automated export back to Google Drive.
- **Verification**: Run headless test of the Colab workflow commands; verify output artifact schemas match the host and sidecar specifications.

### Phase 4: End-to-End Integration & Quality Gate Validation (P1)
- **Goal**: Connect end-to-end video upload in the frontend to the real reconstruction pipeline, compute real photogrammetric QA metrics (reprojection error, point density), and display them in the AI Quality Gate card.
- **Changes**:
  - Integrate real progress reporting from stages to the frontend state machine.
  - Compute actual reprojection errors and point counts for `stage7_quality_gate.py`.
- **Verification**: Upload real drone video, verify full end-to-end execution without any mock fallbacks.
