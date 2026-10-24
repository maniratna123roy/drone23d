"""VantageCam v1 — Polycam-Equivalent Drone Video to 3D Reconstruction Sidecar.

A non-invasive sidecar service implementing the key technical capabilities
identified from Polycam research:
- Parallax-based keyframe extraction
- Dual output (mesh + Gaussian splats) from the same input
- GPS georeferencing via Umeyama alignment
- Dynamic object masking
- Orthomosaic / DSM / LAZ generation
- Automated quality gate with retry ladder
- Optional foundation model reconstruction (DUSt3R / MASt3R)

Runs independently on port 8002 (main backend: 8000, videogrammetry: 8001).
"""

__version__ = "1.0.0"
