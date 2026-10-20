"""Quality tiers for Videogrammetry Sidecar.
Implements the 4 configuration tiers defined in System Architecture Section 6:
- Lite: quick preview, coarse mesh
- Standard: operational documentation
- Premium: measurement-grade mesh and point cloud
- Premium Advanced: maximum detail, automatic redo loop
"""

from typing import Dict, Any
from pydantic import BaseModel, Field

class TierConfig(BaseModel):
    id: str
    name: str
    description: str
    frame_budget: int
    resolution_label: str
    max_dimension: int
    dynamic_masks: bool
    qa_max_retries: int
    triangle_budget: int
    texture_resolution: int
    intended_output: str
    matching_window: int = 15

TIERS: Dict[str, TierConfig] = {
    "lite": TierConfig(
        id="lite",
        name="Lite",
        description="Fast preview for rapid reconnaissance and coarse mesh checks.",
        frame_budget=200,
        resolution_label="1080p",
        max_dimension=1920,
        dynamic_masks=False,
        qa_max_retries=0,
        triangle_budget=50_000,
        texture_resolution=2048,
        intended_output="Quick 3D preview, coarse mesh",
        matching_window=10,
    ),
    "standard": TierConfig(
        id="standard",
        name="Standard",
        description="Balanced operational documentation tier for engineering and inspections.",
        frame_budget=400,
        resolution_label="4K",
        max_dimension=3840,
        dynamic_masks=False,
        qa_max_retries=1,
        triangle_budget=250_000,
        texture_resolution=4096,
        intended_output="Operational documentation, textured mesh, point cloud",
        matching_window=15,
    ),
    "premium": TierConfig(
        id="premium",
        name="Premium",
        description="High-fidelity measurement-grade mesh and point cloud with dynamic-object masking.",
        frame_budget=700,
        resolution_label="4K to 8K",
        max_dimension=4096,
        dynamic_masks=True,
        qa_max_retries=2,
        triangle_budget=750_000,
        texture_resolution=8192,
        intended_output="Measurement-grade mesh, point cloud, orthomosaic",
        matching_window=20,
    ),
    "premium_advanced": TierConfig(
        id="premium_advanced",
        name="Premium Advanced",
        description="Survey-grade reconstruction with scene tiling, 8K textures, and automatic AI redo loop.",
        frame_budget=1500,
        resolution_label="8K and above (tiled)",
        max_dimension=7680,
        dynamic_masks=True,
        qa_max_retries=3,
        triangle_budget=2_000_000,
        texture_resolution=8192,
        intended_output="Maximum detail 3D model, tiled LODs, sub-centimeter orthomosaic",
        matching_window=30,
    ),
}

def get_tier(tier_id: str) -> TierConfig:
    return TIERS.get(tier_id.lower(), TIERS["standard"])
