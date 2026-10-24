"""VantageCam v1 Pipeline Stages (0-8).

10-stage drone video to 3D reconstruction pipeline:
0. Probe — Validate video input, extract metadata
1. Parallax Frames — Extract keyframes using parallax-based filtering
2. Dynamic Masking — Remove dynamic objects (people, vehicles, etc.)
3. SfM — Structure-from-Motion with GPS prior (Umeyama alignment)
4. Dense — Dense depth map estimation
5a. Mesh — Mesh generation and texturing
5b. Splats — Gaussian splatting (dual path from same sparse cloud)
6. Georef — Orthomosaic, DSM, LAZ generation
7. Quality Gate — Automated quality evaluation + retry ladder
8. Export — Package final artifacts (manifest.json, web viewer)
"""

__all__ = []
