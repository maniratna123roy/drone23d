# Spatial Twin — Beginner's ML Developer Guide 🛰️🤖

> **Welcome to the Spatial Twin ML Pipeline!**  
> If you are new to ML engineering, don't worry: in this project, **you do not need to build complex neural networks from scratch or write mathematical loss functions.**  
> Everything is designed as modular, automated steps using industry-standard pretrained models and geometric optimization.

---

## 1. The Three AI Systems Explained

| Component | Technology | Real-World Analogy | Training Required? |
|---|---|---|---|
| **Visual Reconstruction** | 3D Gaussian Splatting (`gsplat`) | Sculpting a 3D statue out of ~1.5 million tiny colored mist droplets based on camera angles | **Geometric Optimization** (fits to the photos, done once offline) |
| **Semantic Vision** | `SegFormer-B0` (NVIDIA / Hugging Face) | An instant coloring book that colors buildings blue, roads grey, and trees green | **Zero** (Pretrained model, inference only) |
| **Natural Language** | `Qwen2.5-3B` (Alibaba / Ollama) | A strict waiter who writes English orders onto a structured paper order form | **Zero** (Prompting with strict JSON schema) |

---

## 2. Hardware Strategy: Laptop vs Cloud GPU

- **Your Laptop:** NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM).
- **The Reality:** 
  - **Live Demo Runtime:** Perfectly suited for running the FastAPI backend, Ollama `qwen2.5:3b`, and the Three.js 3D viewer in the browser simultaneously.
  - **3DGS Training:** Training 3D Gaussian Splats on high-resolution drone photos typically requires 10–14 GB VRAM during densification. Doing this locally on 4 GB would crash with CUDA Out-Of-Memory (OOM).
- **The Solution (Plan B / Decision D16):**
  - We train the 3DGS scene on **Google Colab (Free T4 GPU with 15 GB VRAM)**.
  - Colab runs the optimization in ~25–35 minutes and produces `point_cloud.ply`.
  - You download `point_cloud.ply` and place it in `output/mill/point_cloud.ply`.

---

## 3. End-to-End Pipeline Steps (Step-by-Step)

```
[Drone Photos + Poses] ──(Google Colab 3DGS)──► point_cloud.ply
                                                        │
[Keyframe Photos] ──────(SegFormer-B0)────────► masks/*.png
                                                        │
                         ┌──────────────────────────────┘
                         ▼
        [Stage 04: Project Masks to 3D] ───────► labels.npy
                         │
        [Stage 05a: RANSAC Ground Fit] ────────► Ground at z=0, Z-up
                         │
        [Stage 05b: DBSCAN + Alpha-Shape] ─────► Building Footprints & Heights
                         │
        [Stage 06: PostGIS Loader] ────────────► structures table populated
                         │
        [Stage 07: Binary Exporter] ───────────► scene.splat + scene.classes.u8
```

### Step 1: 3DGS Reconstruction (in Google Colab)
1. Open Google Colab (https://colab.research.google.com).
2. Set Runtime: **Runtime > Change runtime type > T4 GPU**.
3. Run the notebook `pipeline/02_train_colab.ipynb` (provided in this repository).
4. Download the resulting `point_cloud.ply` (or `.splat`) into `output/mill/`.

### Step 2: Semantic Segmentation (`pipeline/03_segment.py`)
- Takes sample keyframe images from the drone dataset.
- Loads `nvidia/segformer-b0-finetuned-cityscapes-1024-1024` from Hugging Face (~14 MB).
- Saves color-coded class masks in `output/masks/`:
  - `0`: Structure / Building
  - `1`: Terrain / Ground
  - `2`: Road
  - `3`: Vegetation / Trees
  - `255`: Unknown

### Step 3: Project 2D Labels to 3D Splats (`pipeline/04_label_splats.py`)
- For each 3D splat, projects its XYZ coordinate back onto the camera views.
- Reads the mask color at that pixel and assigns the majority vote class.
- Saves `output/mill/labels.npy`.

### Step 4: Fit Ground Plane & Coordinate Frame (`pipeline/05a_fit_ground_frame.py`)
- Uses RANSAC (Random Sample Consensus) on terrain/road splats to find the flat ground.
- Rotates the entire scene so that:
  - Ground plane is exactly at `z = 0`.
  - Normal vector points directly `+Z` up.
  - Units are scaled to metric meters.

### Step 5: Extract Building Footprints & Heights (`pipeline/05b_extract_geometry.py`)
- Filters splats belonging to `class 0` (Structures).
- Runs **DBSCAN** clustering (density-based spatial clustering) to group splats into distinct buildings.
- Uses **Alpha-Shape** or **Convex Hull** to compute the 2D polygon footprint.
- Calculates height: `Height = 95th percentile(Z) - ground(0)`.
- Calculates area and estimated volume.

### Step 6: Load into Database (`pipeline/06_load_db.py`)
- Inserts each building into the PostGIS `structures` table with its exact GeoJSON polygon and 3D bounding box (`splat_bbox`).
- Assigns geographic regions (`center`, `north`, `south`, `east`, `west`).

### Step 7: Export Web-Ready Splat Assets (`pipeline/07_export_splat.py`)
- Exports `static/scene.splat` (compact binary format for Three.js).
- Exports `static/scene.classes.u8` (exact 1-byte-per-splat class sidecar).

---

## 4. Key Rules for the ML Engineer
1. **Never rename point order:** The index of a splat in `scene.splat` must match its index in `scene.classes.u8` 1:1.
2. **Keep the Live Demo lightweight:** The offline pipeline does the heavy lifting once. The live demo app only runs the lightweight Qwen2.5-3B model and the Three.js renderer.
3. **Use the Seed Data during development:** The full backend and frontend can run on seed data (`db/seed.sql`) while you work on the ML dataset in parallel!
