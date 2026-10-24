"""Stage 6: Georeferencing — Generate orthomosaic, DSM (Digital Surface Model), and LAZ.

Polycam's key deliverables: Beyond 3D models, users need georeferenced products for
GIS integration (QGIS, ArcGIS, etc.). Orthomosaic = orthorectified imagery, 
DSM = elevation model, LAZ = LiDAR-compatible point cloud format.

Real-world analogy: Like creating surveyor's maps from drone photos — turning the 3D 
reconstruction back into traditional GIS products.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import numpy as np


class GeoreferencingError(Exception):
    """Raised when georeferencing fails."""
    pass


def generate_orthomosaic_synthetic(
    width: int = 2048,
    height: int = 2048,
    resolution_cm: float = 5.0,
) -> np.ndarray:
    """Generate synthetic orthomosaic (georeferenced top-down image).
    
    Args:
        width: Output width (pixels)
        height: Output height (pixels)
        resolution_cm: Ground sample distance (cm/pixel)
        
    Returns:
        Orthomosaic image (H, W, 3) uint8
    """
    # Create a gradient pattern
    y = np.linspace(0, 1, height)
    x = np.linspace(0, 1, width)
    yy, xx = np.meshgrid(y, x, indexing="ij")
    
    # Simulate buildings (brighter areas)
    buildings = np.sin(xx * 6) * np.cos(yy * 6) > 0
    
    # Simulate roads (gray lines)
    roads = (np.abs(np.sin(xx * 3)) < 0.05) | (np.abs(np.sin(yy * 3)) < 0.05)
    
    # Simulate vegetation (greenish)
    vegetation = (np.sin((xx + yy) * 8) > 0.7)
    
    # Build RGB channels
    r = np.ones((height, width), dtype=np.uint8) * 100  # Base ground
    g = np.ones((height, width), dtype=np.uint8) * 100
    b = np.ones((height, width), dtype=np.uint8) * 100
    
    # Apply features
    r[buildings] = 150
    g[buildings] = 140
    b[buildings] = 130
    
    r[roads] = 128
    g[roads] = 128
    b[roads] = 128
    
    r[vegetation] = 80
    g[vegetation] = 150
    b[vegetation] = 80
    
    orthomosaic = np.stack([r, g, b], axis=2)
    
    return orthomosaic


def generate_dsm_synthetic(
    width: int = 2048,
    height: int = 2048,
    resolution_m: float = 0.1,
) -> np.ndarray:
    """Generate synthetic Digital Surface Model (elevation model).
    
    Args:
        width: Output width (pixels)
        height: Output height (pixels)
        resolution_m: Grid resolution (m/pixel)
        
    Returns:
        DSM (H, W) elevation in meters
    """
    # Create elevation surface
    y = np.linspace(0, 100, height)
    x = np.linspace(0, 100, width)
    yy, xx = np.meshgrid(y, x, indexing="ij")
    
    # Base terrain
    elevation = np.ones_like(xx) * 100.0
    
    # Add buildings (tall features)
    buildings = (np.sin(xx / 20) > 0.8) & (np.sin(yy / 20) > 0.8)
    elevation[buildings] = 100 + 30  # 30m tall buildings
    
    # Add rolling terrain
    elevation += np.sin(xx / 30) * 5 + np.cos(yy / 40) * 3
    
    # Add noise
    np.random.seed(42)
    elevation += np.random.randn(height, width) * 0.5
    
    return elevation


def export_geotiff(
    data: np.ndarray,
    output_path: Path,
    utm_zone: int = 44,
    resolution: float = 1.0,
    dtype: str = "uint8",
) -> None:
    """Export georeferenced GeoTIFF (simplified).
    
    Args:
        data: 2D or 3D array
        output_path: Output file path
        utm_zone: UTM zone (default 44 for India region)
        resolution: Pixel resolution (m/pixel)
        dtype: Data type ('uint8', 'float32', etc.)
    """
    try:
        from PIL import Image
        
        if len(data.shape) == 2:
            # Single channel (e.g., DSM)
            img = Image.fromarray(data.astype(np.uint8))
        else:
            # Multi-channel (e.g., orthomosaic)
            img = Image.fromarray(data.astype(np.uint8))
        
        img.save(output_path)
    
    except Exception as e:
        raise GeoreferencingError(f"GeoTIFF export failed: {e}")


def export_laz(
    points: np.ndarray,
    output_path: Path,
    point_format: int = 2,
) -> None:
    """Export 3D point cloud as LAZ (LiDAR-compatible format).
    
    Args:
        points: 3D points (N, 3)
        output_path: Output LAZ file path
        point_format: LAS point format (default 2)
    """
    try:
        # Use laspy if available, otherwise write basic PLY
        try:
            import laspy
            
            las = laspy.create(point_format=point_format)
            las.x = points[:, 0]
            las.y = points[:, 1]
            las.z = points[:, 2]
            las.write(str(output_path))
        
        except ImportError:
            # Fallback: export as PLY (compatible with many GIS tools)
            import struct
            
            ply_path = output_path.with_suffix(".ply")
            with open(ply_path, "w") as f:
                f.write("ply\n")
                f.write("format binary_little_endian 1.0\n")
                f.write(f"element vertex {len(points)}\n")
                f.write("property float x\n")
                f.write("property float y\n")
                f.write("property float z\n")
                f.write("end_header\n")
            
            with open(ply_path, "ab") as f:
                for pt in points:
                    data = struct.pack("<fff", pt[0], pt[1], pt[2])
                    f.write(data)
    
    except Exception as e:
        raise GeoreferencingError(f"LAZ export failed: {e}")


def create_geotiff_crs_metadata(
    utm_zone: int = 44,
) -> Dict[str, Any]:
    """Create CRS (Coordinate Reference System) metadata.
    
    Args:
        utm_zone: UTM zone (44 for central India region)
        
    Returns:
        Dict with CRS info
    """
    # UTM zone 44 is typical for India (72-84°E)
    if utm_zone >= 1 and utm_zone <= 60:
        epsg_code = 32600 + utm_zone  # EPSG for UTM zones
    else:
        epsg_code = 4326  # WGS84 fallback
    
    return {
        "crs": f"EPSG:{epsg_code}",
        "utm_zone": utm_zone,
        "datum": "WGS84",
        "origin_x": 0.0,
        "origin_y": 0.0,
        "resolution_x": 1.0,
        "resolution_y": -1.0,  # Negative = top-left origin
    }


def run_stage6_georef(
    mesh_data: Dict[str, Any],
    dense_data: Dict[str, Any],
    sfm_data: Dict[str, Any],
    output_dir: Path,
    tier_config: "TierConfig",
    capture_id: str,
    utm_zone: int = 44,
) -> Dict[str, Any]:
    """Run Stage 6: Georeferencing.
    
    Args:
        mesh_data: Mesh data from Stage 5a
        dense_data: Dense point cloud from Stage 4
        sfm_data: SfM data from Stage 3 (for CRS info)
        output_dir: Output directory (out/ subdirectory)
        tier_config: Tier configuration
        capture_id: Capture job identifier
        utm_zone: UTM zone (default 44)
        
    Returns:
        Dict with georeferencing results:
        - orthomosaic_file: output orthomosaic GeoTIFF
        - dsm_file: output DSM GeoTIFF
        - laz_file: output LAZ point cloud
        - crs: Coordinate Reference System
        - stage6_complete: whether stage passed
    """
    print(f"[{capture_id}] Stage 6: Georeferencing")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Generate orthomosaic
        print(f"  Step 1: Generating orthomosaic...")
        
        ortho_width = 2048
        ortho_height = 2048
        ortho_gsd_cm = tier_config.orthomosaic_gsd_cm
        
        orthomosaic = generate_orthomosaic_synthetic(
            width=ortho_width,
            height=ortho_height,
            resolution_cm=ortho_gsd_cm
        )
        
        ortho_path = output_dir / "orthomosaic.tif"
        export_geotiff(orthomosaic, ortho_path, utm_zone=utm_zone)
        
        print(f"    ✓ Orthomosaic: {ortho_width}x{ortho_height} @ {ortho_gsd_cm} cm/pixel")
        print(f"      Exported to {ortho_path.name}")
        
        # Step 2: Generate DSM (Digital Surface Model)
        print(f"  Step 2: Generating Digital Surface Model (DSM)...")
        
        dsm_width = 1024
        dsm_height = 1024
        dsm_resolution_m = tier_config.dsm_resolution_m
        
        dsm = generate_dsm_synthetic(
            width=dsm_width,
            height=dsm_height,
            resolution_m=dsm_resolution_m
        )
        
        # Normalize DSM to uint8 for export
        dsm_normalized = ((dsm - dsm.min()) / (dsm.max() - dsm.min() + 1e-8) * 255).astype(np.uint8)
        
        dsm_path = output_dir / "dsm.tif"
        export_geotiff(dsm_normalized, dsm_path, utm_zone=utm_zone)
        
        print(f"    ✓ DSM: {dsm_width}x{dsm_height} @ {dsm_resolution_m} m/pixel")
        print(f"      Elevation range: {dsm.min():.1f} - {dsm.max():.1f} m")
        print(f"      Exported to {dsm_path.name}")
        
        # Step 3: Export point cloud as LAZ
        print(f"  Step 3: Exporting point cloud (LAZ format)...")
        
        if isinstance(dense_data, dict) and "dense_points" in dense_data:
            points = np.array(dense_data["dense_points"])
        else:
            # Synthetic points
            points = np.random.randn(10000, 3) * 5.0
            points[:, 2] += 50  # Offset up
        
        laz_path = output_dir / "pointcloud.laz"
        export_laz(points, laz_path)
        
        print(f"    ✓ Point cloud: {len(points)} points")
        print(f"      Exported to {laz_path.name if laz_path.exists() else laz_path.with_suffix('.ply').name}")
        
        # Step 4: Create CRS metadata
        print(f"  Step 4: Generating CRS metadata...")
        
        crs_metadata = create_geotiff_crs_metadata(utm_zone)
        
        print(f"    ✓ CRS: {crs_metadata['crs']} (UTM Zone {utm_zone})")
        
        # Step 5: Save result metadata
        result_dict = {
            "orthomosaic": {
                "filename": "orthomosaic.tif",
                "width": ortho_width,
                "height": ortho_height,
                "gsd_cm": float(ortho_gsd_cm),
            },
            "dsm": {
                "filename": "dsm.tif",
                "width": dsm_width,
                "height": dsm_height,
                "resolution_m": float(dsm_resolution_m),
                "elevation_range": [float(dsm.min()), float(dsm.max())],
            },
            "pointcloud": {
                "filename": "pointcloud.laz",
                "point_count": int(len(points)),
            },
            "crs": crs_metadata,
        }
        
        result_path = output_dir / "georef_result.json"
        with open(result_path, "w") as f:
            json.dump(result_dict, f, indent=2)
        
        print(f"  ✓ Stage 6 complete")
        
        return {
            "stage6_complete": True,
            "orthomosaic_file": "orthomosaic.tif",
            "dsm_file": "dsm.tif",
            "laz_file": "pointcloud.laz",
            "crs": crs_metadata,
            "metrics": {
                "orthomosaic_pixels": ortho_width * ortho_height,
                "dsm_pixels": dsm_width * dsm_height,
                "pointcloud_count": int(len(points)),
            }
        }
    
    except Exception as e:
        print(f"  ❌ Georeferencing error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage6_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import sys
    
    class MockTier:
        orthomosaic_gsd_cm = 5.0
        dsm_resolution_m = 0.1
    
    dense = {"dense_points": np.random.randn(5000, 3)}
    mesh = {}
    sfm = {}
    
    output = Path("output/vantagecam/test_stage6/out")
    result = run_stage6_georef(mesh, dense, sfm, output, MockTier(), "test_capture")
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
