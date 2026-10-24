"""Quality tiers for VantageCam v1 Sidecar.
Implements 4 configuration tiers mirroring Polycam's service tiers:
- Lite: rapid preview
- Standard: operational use
- Premium: measurement-grade
- Premium Advanced: survey-grade with AI loop
"""

from typing import Dict
from pydantic import BaseModel


class TierConfig(BaseModel):
    """Configuration for a quality tier.
    
    Real-world analogy: Like restaurant menus — same kitchen, different plating.
    Lite = quick snack, Premium = multi-course feast.
    """
    id: str
    """Tier identifier (lowercase)."""
    
    name: str
    """Human-readable tier name."""
    
    description: str
    """Marketing-friendly description."""
    
    frame_budget: int
    """Max keyframes to extract (after parallax filtering)."""
    
    resolution_label: str
    """Input resolution guidance (e.g., '1080p', '4K')."""
    
    max_dimension: int
    """Max image width/height to use (rest downsampled)."""
    
    dynamic_masks: bool
    """Enable stage 2 dynamic object masking (SegFormer)."""
    
    qa_max_retries: int
    """Max attempts if quality gate fails (stage 7)."""
    
    mesh_triangle_budget: int
    """Max triangles for stage 5a mesh output."""
    
    splat_count_target: int
    """Target Gaussian splat count for stage 5b."""
    
    texture_resolution: int
    """Texture atlas resolution (e.g., 2048, 4096, 8192)."""
    
    orthomosaic_gsd_cm: float
    """Orthomosaic Ground Sample Distance (cm/pixel)."""
    
    dsm_resolution_m: float
    """Digital Surface Model resolution (m/pixel)."""
    
    intended_output: str
    """What outputs the user should expect."""
    
    matching_window: int = 15
    """SfM feature matching search window (frames)."""


# Define the 4 tiers
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
        mesh_triangle_budget=50_000,
        splat_count_target=50_000,
        texture_resolution=2048,
        orthomosaic_gsd_cm=10.0,
        dsm_resolution_m=0.5,
        intended_output="Quick 3D preview, coarse mesh, splats",
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
        mesh_triangle_budget=250_000,
        splat_count_target=250_000,
        texture_resolution=4096,
        orthomosaic_gsd_cm=5.0,
        dsm_resolution_m=0.2,
        intended_output="Operational documentation, textured mesh, point cloud, orthomosaic",
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
        mesh_triangle_budget=750_000,
        splat_count_target=750_000,
        texture_resolution=8192,
        orthomosaic_gsd_cm=2.5,
        dsm_resolution_m=0.1,
        intended_output="Measurement-grade mesh, point cloud, orthomosaic, DSM",
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
        mesh_triangle_budget=2_000_000,
        splat_count_target=2_000_000,
        texture_resolution=8192,
        orthomosaic_gsd_cm=1.0,
        dsm_resolution_m=0.05,
        intended_output="Maximum detail 3D model, tiled LODs, sub-centimeter orthomosaic",
        matching_window=30,
    ),
}


def get_tier(tier_id: str) -> TierConfig:
    """Look up a tier configuration by ID, default to 'standard'."""
    return TIERS.get(tier_id.lower(), TIERS["standard"])


def list_tiers() -> Dict[str, TierConfig]:
    """Return all available tiers."""
    return TIERS.copy()
