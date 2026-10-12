# Spatial Twin — 5-Minute Demo Script

> This rehearsed script drives the live demo presentation.

## 0:00–0:30 — The Hook & Problem
- "Drone videos are dead pixels. A drone can fly over a city or construction site, but a video cannot tell you which buildings are taller than 20 metres or simulate raising the skyline."
- "Today, answering those questions requires LiDAR, survey crews, or expensive CAD modelling."

## 0:30–1:30 — The Architecture & Solution
- Show the 3-layer architecture:
  1. **Visual Layer:** Photorealistic 3D Gaussian Splatting scene (~1.5M splats) running directly in the browser via Three.js.
  2. **Intelligence Layer:** PostGIS spatial database tracking every structure's footprint, height, volume, and edit history in true Cartesian metres.
  3. **Translation Engine:** Local LLM (Qwen2.5-3B via Ollama) converting natural English strictly into validated intent JSON — never raw SQL.

## 1:30–2:30 — Live Query
- Orbit the photorealistic scene.
- Type in the Query Box: `"Which buildings are taller than 20 metres?"`
- Result (< 3s): Matching buildings light up in 3D, and the metrics table populates with real heights, areas, and volumes.
- Click an object to reveal the Object Inspector panel.

## 2:30–3:30 — Live Edit with Ghost Before/After
- Type in the Edit Box: `"Raise the two central buildings by 40 metres"`
- Show the Preview banner with calculated height deltas (+40 m).
- Click **Confirm**:
  - The skyline dynamically rises with a new procedural mesh.
  - The underlying splats are masked.
  - The original geometry remains visible as a semi-transparent "ghost" overlay.
  - If a second tab is open, show instantaneous WebSocket synchronization.

## 3:30–4:15 — Instant Undo & Safety
- Click **Undo**:
  - The database rolls back the transaction.
  - The procedural mesh vanishes and the original splats re-appear immediately.
- Type nonsense or test an injection string: show friendly validation error with zero state corruption.

## 4:15–5:00 — Status, VRAM & Summary
- Expand the System Status panel: display real-time VRAM (~3.2 GB total), active model, service health, and the exact compiled SQL.
- Conclude: "A fully local, editable, photorealistic spatial digital twin running on a single laptop."
