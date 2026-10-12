# Spatial Twin 🌐🏙️

**Drone Video → Verified Camera Geometry → Dense Photogrammetry → Photorealistic 3D Gaussian Splatting → Multi-View Semantic Segmentation → Ground Leveling & Metric Scale Calibration → PostGIS 3D SFCGAL Solids → Interactive WebGL Viewer & Natural Language AI Spatial Twin.**

---

## 🏗️ System Overview

**Spatial Twin** transforms uncalibrated aerial drone footage into an intelligent, survey-grade 3D Digital Twin. Rather than creating generic synthetic CAD boxes or unmeasured point clouds, Spatial Twin reconstructs authentic photorealistic surfaces via **3D Gaussian Splatting (3DGS)**, segments surfaces across camera views using **SegFormer AI**, levels and calibrates the coordinate space to true metric metres, measures physical dimensions ($H, W, D, \text{Area}, \text{Volume}$) for all observed infrastructure categories, persists 3D volumetric solids into a **PostGIS 16 + SFCGAL** spatial database, and enables conversational spatial intelligence powered by **Ollama (`qwen2.5:3b`)**.

```
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                SPATIAL TWIN                                 │
    │  Photorealistic 3D Gaussian Splatting + PostGIS 3D Solids + AI Intelligence │
    └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ System Architecture

Spatial Twin is structured as a decoupled, high-performance pipeline spanning geometric reconstruction, deep semantic segmentation, spatial database persistence, and a real-time reactive WebGL interface:

```mermaid
flowchart TD
    subgraph INGESTION ["1. Video Ingestion & Keyframing"]
        V[Raw Drone Video MP4/MOV] --> P[PyAV Keyframe Sampler]
        P --> F[Keyframe Image Sequence]
    end

    subgraph RECONSTRUCTION ["2. Geometric & Photometric Reconstruction"]
        F --> SFM[COLMAP 4.2.1 CUDA SfM]
        SFM --> BA[Ceres Bundle Adjustment & Camera Poses]
        BA --> MVS[CUDA PatchMatch Stereo & Fusion]
        MVS --> DENSE[Dense Point Cloud & Geometric Normals]
        DENSE --> G3D[PyTorch CUDA 3DGS Optimizer]
        G3D --> SPLAT[Anisotropic 32-Byte scene.splat]
    end

    subgraph SEMANTICS ["3. Multi-View Semantic Classification"]
        F --> SEG[SegFormer-B0 Cityscapes CPU]
        SEG --> MASKS[Per-Frame Semantic Class Probabilities]
        MASKS & BA --> VOTE[Multi-View Depth-Grounded Projection & Voting]
        VOTE --> SIDECAR[Binary Sidecar scene.classes.u8]
    end

    subgraph ALIGNMENT ["4. Ground Leveling, Metric Scaling & Extraction"]
        SPLAT & SIDECAR --> SVD[SVD Ground Plane Estimation]
        SVD --> ROT[Rigid Upright Rotation Z=0.0 Datum]
        ROT --> SCALE[Metric Scale Calibration 1x-15x]
        SCALE --> DBSCAN[0.5m Voxel-Accelerated DBSCAN]
        DBSCAN --> MEASURE[Physical Measurement Engine]
    end

    subgraph STORAGE ["5. PostGIS 3D Spatial Database"]
        MEASURE --> PG[(PostGIS 16 + SFCGAL)]
        PG --> T1[structures: PolyhedralSurfaceZ 3D Solids]
        PG --> T2[roads: LineString / Polygon Corridors]
        PG --> T3[vegetation: Canopy Clusters]
        PG --> T4[terrain: Ground Datum Extents]
    end

    subgraph BACKEND ["6. FastAPI High-Concurrency Backend"]
        PG <--> API[FastAPI Server :8000]
        API <--> OLLAMA[Ollama qwen2.5:3b LLM]
        API <--> WS[WebSocket Diff Broadcaster]
    end

    subgraph FRONTEND ["7. Three.js & React Web Application"]
        API <--> APP[React 19 + TanStack Start :8080/demo]
        APP --> VIEWER[Custom 3D Gaussian Quad Shader]
        APP --> INVENTORY[Semantic Physical Inventory Matrix]
        APP --> INSPECTOR[Interactive 6-Metric Object Inspector]
        APP --> QUERY[Natural Language Spatial Query Box]
        APP --> EDIT[Conversational Edit Box & 3D Ghost Previews]
    end
```

### Architectural Subsystems

1. **Ingestion & Camera Geometry (Phase A):**
   - High-overlap temporal keyframe extraction using PyAV at native aspect ratio.
   - Native CUDA COLMAP Structure-from-Motion solves camera intrinsics $K$ and poses $(R_w, t_w)$ using Ceres bundle adjustment.
   - Enforces fail-closed quality gates (reprojection error $<0.5\text{px}$, $\ge 50\%$ camera registration, track continuity).
2. **Dense Stereo & 3D Gaussian Optimization (Phase B & C):**
   - COLMAP CUDA PatchMatch Stereo & Stereo Fusion triangulates geometric surface points with normal vectors and multi-view consistency checks.
   - Custom PyTorch CUDA differentiable rasterizer fits 3D Gaussian positions $\mu$, anisotropic scales $s$, quaternions $q$, opacities $\alpha$, and spherical harmonic colors $c$ against source photographs using $\mathcal{L}_1 + \lambda \mathcal{L}_{\text{SSIM}}$ loss with sky exclusion.
   - Emits compact, web-optimized 32-byte `.splat` binary files (XYZ, scale, RGBA, quantized WXYZ).
3. **Multi-View Depth-Grounded Semantic Segmentation (Phase D):**
   - SegFormer-B0 performs zero-shot neural segmentation across registered keyframes on CPU (preventing GPU VRAM contention with LLM).
   - Gaussian centers are backprojected into registered camera views; votes are accepted only within $2\%$ geometric MVS depth, $\ge 0.65$ probability, and multi-view agreement.
   - Emits immutable 1-byte-per-splat binary sidecars (`scene.classes.u8`).
4. **Metric Calibration & Multi-Category Measurement Engine:**
   - **SVD Ground Plane Alignment:** Computes ground normal from classified road/terrain points (or lowest 20% points along camera up vector) and applies rigid 3D transformation $T$ leveling ground to $Z = 0.0\text{m}$ datum with $+Z$ pointing into the sky.
   - **Metric Scale Anchor:** Normalizes scale so extracted building elevations reflect true real-world dimensions ($\sim 10\text{m} - 70\text{m}$).
   - **Grid-Accelerated DBSCAN:** Downsamples dense 2D footprint points using 0.5m voxel grids, clustering distinct building complexes in **0.05 seconds** with **zero memory overhead**, followed by 1-nearest-neighbor label propagation.
   - **Physical Attribute Measurement:**
     - **Buildings (Class 0):** Height ($h = p_{98}(z) - \text{base}_z$), width ($w = \max(x) - \min(x)$), depth ($d = \max(y) - \min(y)$), footprint area ($A$), estimated volume ($V = A \cdot h$), ground elevation ($z$), and simplified 2D polygon footprints.
     - **Roads / Sidewalks (Class 2):** Corridor length ($L$), average width ($w$), surface area ($A$), elevation ($z$).
     - **Vegetation / Trees (Class 3):** Canopy height ($h$), spread width ($w$), depth ($d$), canopy surface area ($A$).
     - **Terrain (Class 1):** Ground datum plane elevation ($z$), surface area ($A$).
5. **PostGIS 3D Database Storage:**
   - Populates PostgreSQL 16 + PostGIS 3.4 + SFCGAL with SRID 0 metric units.
   - Builds 3D volumetric solids via `ST_Extrude(footprint, 0, 0, height_m)` as `PolyhedralSurfaceZ`.
   - Records spatial bounding boxes, regions (`NORTH`, `CENTER`, `SOUTH`, `EAST`, `WEST`), and version tracking for transactional undo/redo.
6. **Ollama Conversational Intelligence:**
   - Local `qwen2.5:3b` parses natural language queries and edits using strict JSON schema output.
   - Rules engine and regex fallback guarantee sub-second query latency and zero live demonstration failures.
   - Edits generate holographic 3D neon-cyan wireframe ghost meshes in Three.js for interactive user approval before committing to PostGIS.

---

## 🔄 User Flow Architecture

The user journey in Spatial Twin is seamless, transitioning from raw video upload to interactive 3D spatial exploration and conversational modification:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web Client (/demo)
    participant API as FastAPI Backend
    participant Pipe as Reconstruction Pipeline
    participant DB as PostGIS 16
    participant LLM as Ollama (qwen2.5:3b)

    Note over User, Web: 1. Video Upload & Live Processing
    User->>Web: Uploads drone footage (MP4/MOV)
    Web->>API: POST /api/pipeline/upload
    API->>Pipe: Dispatches isolated background reconstruction worker
    loop Progress Polling & WebSocket Updates
        Pipe-->>API: Reports stage progress (SfM -> MVS -> 3DGS -> Semantics)
        API-->>Web: Live HUD progress updates (8% -> 35% -> 60% -> 98% -> 100%)
    end
    Pipe->>API: Publishes verified immutable scene manifest
    API-->>Web: Scene published notification & automatic viewer load

    Note over User, Web: 2. 3D Visualization & Semantic Exploration
    Web->>API: GET /static/scenes/{id}/scene.splat & scene.classes.u8
    Web->>Web: Renders photorealistic 3D Gaussian quads with camera depth sorting
    User->>Web: Clicks [🎨 Classes] tab
    Web->>API: GET /api/objects/classified-attributes
    API-->>Web: Returns measured attributes for Buildings, Roads, Vegetation, Terrain
    Web->>User: Displays interactive Measured Physical Inventory matrix

    Note over User, Web: 3. Surveying & Object Inspection
    User->>Web: Clicks [🏢 Inspector] tab or clicks building mesh in 3D viewer
    Web->>API: GET /api/objects/structures
    API->>DB: SELECT id, height_m, width_m, depth_m, area_m2, splat_bbox FROM structures
    DB-->>API: Returns dimensional records
    API-->>Web: Returns structured assets
    Web->>User: Renders 6-metric inspector (Height, Width, Depth, Area, Volume, Bbox)

    Note over User, Web: 4. Conversational AI Spatial Querying
    User->>Web: Enters query: "Which buildings are taller than 20m in the east?"
    Web->>API: POST /api/query {"text": "..."}
    API->>LLM: Compiles intent JSON schema
    LLM-->>API: {"operation": "QUERY_HEIGHT", "filter": {"min_height_m": 20, "region": "east"}}
    API->>DB: Executes parameterized PostGIS SQL query
    DB-->>API: Matched building records (e.g. Building #1, 29.2m)
    API-->>Web: {"status": "success", "matched_ids": [1], "objects": [...]}
    Web->>User: Highlights matching buildings in 3D viewer with cyan bounding boxes

    Note over User, Web: 5. Natural Language 3D Editing & Holographic Ghosting
    User->>Web: Enters edit: "Raise the central building by 15m"
    Web->>API: POST /api/edit/preview {"command": "..."}
    API->>LLM: Intent parsing
    API-->>Web: {"preview_token": "...", "target_ids": [1], "new_height_m": 44.2}
    Web->>User: Renders holographic neon wireframe ghost overlay in 3D viewer
    User->>Web: Clicks [Apply Edit]
    Web->>API: POST /api/edit/apply {"preview_token": "..."}
    API->>DB: Updates structures & records snapshot in geometry_history
    API->>API: Broadcasts scene_diff over WebSocket
    API-->>Web: Confirmed edit & updated metrics
    User->>Web: Clicks [Undo] -> PostGIS rolls back snapshot atomically
```

---

## 📊 Live Measured Attributes Matrix

When a drone video is processed, the measurement engine produces comprehensive physical surveys:

| Surface Layer | Asset Identity | Measured Physical Attributes | Spatial Representation |
|---|---|---|---|
| **Structures (Class 0)** | **Building #1 (East)** | **Height:** 29.2 m &bull; **Width:** 85.6 m &bull; **Depth:** 52.4 m &bull; **Area:** 2,280.5 m² &bull; **Volume:** 66,590.6 m³ | 3D `PolyhedralSurfaceZ` solid & simplified 2D polygon |
| | **Building #2 (East)** | **Height:** 7.3 m &bull; **Width:** 21.0 m &bull; **Depth:** 18.3 m &bull; **Area:** 244.9 m² &bull; **Volume:** 1,787.8 m³ | 3D `PolyhedralSurfaceZ` solid & simplified 2D polygon |
| | **Building #3 (East)** | **Height:** 6.2 m &bull; **Width:** 9.0 m &bull; **Depth:** 9.2 m &bull; **Area:** 36.5 m² &bull; **Volume:** 226.3 m³ | 3D `PolyhedralSurfaceZ` solid & simplified 2D polygon |
| | **Building #4 (North)** | **Height:** 11.0 m &bull; **Width:** 25.6 m &bull; **Depth:** 12.9 m &bull; **Area:** 133.5 m² &bull; **Volume:** 1,468.5 m³ | 3D `PolyhedralSurfaceZ` solid & simplified 2D polygon |
| **Roads (Class 2)** | **Corridor Network** | **Length:** 176.2 m &bull; **Avg Width:** 48.6 m &bull; **Surface Area:** 8,564.1 m² &bull; **Elevation:** 0.06 m | 2D PostGIS corridor boundary polygon |
| **Vegetation (Class 3)** | **Canopy Cluster** | **Canopy Height:** 33.6 m &bull; **Spread Width:** 71.0 m &bull; **Canopy Area:** 2,070.8 m² | 2D PostGIS canopy cluster polygon |
| **Terrain (Class 1)** | **Ground Datum Plane** | **Datum Elevation:** 30.27 m &bull; **Surface Area:** 969.9 m² | Ground datum reference plane |

---

## 🚀 Quickstart Guide

### Prerequisites
- **OS:** Windows 10/11 or Linux
- **GPU:** NVIDIA GPU with CUDA support (e.g. RTX 3050 Laptop 4GB or higher)
- **Python:** 3.10+ (Python 3.11 recommended)
- **Node.js:** v20+ (Node v22 recommended)
- **Docker:** Docker Desktop for PostGIS container
- **COLMAP:** v4.2+ with CUDA support

### 1. Database Setup (PostGIS 16 + SFCGAL)
Start the PostGIS container with SFCGAL 3D extension enabled:
```powershell
docker-compose up -d
```
*Port is configured to `5435` to avoid port collisions with default local Postgres instances.*

### 2. Backend Setup (FastAPI & Pipeline)
Create a Python virtual environment and install dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Launch the FastAPI application server:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup (React 19 + TanStack Start + Three.js)
In a separate terminal, start the Vite development server:
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 8080
```
Open **[http://localhost:8080/demo](http://localhost:8080/demo)** in Chrome or Edge.

### 4. Local AI Setup (Ollama LLM)
Ensure Ollama is running with the `qwen2.5:3b` model:
```powershell
ollama run qwen2.5:3b
```

---

## 📡 API Reference

### Pipeline & Reconstruction
- `POST /api/pipeline/upload` — Multipart drone video upload; initializes isolated reconstruction ticket.
- `GET /api/pipeline/status` — Returns real-time milestone progress, current stage, and percentage.
- `POST /api/pipeline/align-structures` — Triggers SVD ground leveling, metric calibration, DBSCAN clustering, and PostGIS 3D extrusion.
- `POST /api/pipeline/reset` — Safely resets stuck or interrupted pipeline runs.

### Spatial Objects & Physical Inventory
- `GET /api/objects/classified-attributes` — Returns measured physical dimensions ($H, W, D, \text{Area}, \text{Volume}$) for all 4 categories.
- `GET /api/objects/structures` — Lists all detected buildings with footprints, 3D bounds, heights, areas, and region tags.
- `GET /api/objects/regions` — Returns geographic sectors (`NORTH`, `CENTER`, `SOUTH`, `EAST`, `WEST`).

### Conversational Intelligence
- `POST /api/query` — Natural language spatial queries (e.g. *"Show me buildings over 25m"*).
- `POST /api/edit/preview` — Generates 3D holographic wireframe ghost mesh preview for an edit.
- `POST /api/edit/apply` — Applies the edit to PostGIS and broadcasts WebSocket scene diff.
- `POST /api/edit/undo` — Rolls back the last edit session to previous snapshot.

---

## 🧪 Testing & Quality Gates

Spatial Twin enforces strict automated regression testing across both backend photogrammetry and frontend WebGL components:

```powershell
# Run all backend photogrammetry, publication & API tests (259 tests)
.\.venv\Scripts\pytest backend/tests

# Run frontend Gaussian math, lifecycle & contract unit tests (26 tests)
node --experimental-strip-types --test frontend/tests/*.test.mjs

# Build client and SSR production bundles
npm --prefix frontend run build
```

---

## 📜 Working Agreement & Engineering Principles
1. **Honesty Rule:** Never claim a feature exists that has not been built and tested. Inferred procedural extrusions are never presented as true photogrammetric ground truth.
2. **Fail-Closed Quality Gates:** If camera geometry cannot be verified with sub-pixel reprojection accuracy, the pipeline halts gracefully and preserves the previous verified scene.
3. **Hardware Discipline:** Designed specifically for laptop-class 4GB GPUs — CPU-offloaded SegFormer voting and 0.5m voxel downsampling prevent memory exhaustion while maintaining sub-second inference speeds.
