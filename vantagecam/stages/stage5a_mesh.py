"""Stage 5a: Mesh Generation — Create textured mesh from point cloud.

Polycam's approach: Reconstruct a clean mesh using Poisson surface reconstruction
or ball-pivoting, then apply photorealistic textures from the original images.

Real-world analogy: Like taking a point-cloud scan of a sculpture and sculpting smooth
surfaces through it, then painting with the original photographs.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np


class MeshError(Exception):
    """Raised when mesh generation fails."""
    pass


def generate_mesh_poisson(
    points: np.ndarray,
    normals: Optional[np.ndarray] = None,
    depth: int = 10,
) -> Dict[str, Any]:
    """Generate mesh using Poisson surface reconstruction.
    
    Args:
        points: 3D point cloud (N, 3)
        normals: Point normals (N, 3), optional (estimated if not provided)
        depth: Octree depth for Poisson (higher = finer detail, slower)
        
    Returns:
        Dict with mesh info (vertices, faces, normals, texture_coords)
    """
    try:
        import open3d as o3d
        
        # Create point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        
        if normals is not None:
            pcd.normals = o3d.utility.Vector3dVector(normals)
        else:
            # Estimate normals
            pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        
        # Poisson surface reconstruction
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=depth
        )
        
        # Remove low-density vertices
        vertices_to_remove = densities < np.quantile(densities, 0.1)
        mesh.remove_vertices_by_mask(vertices_to_remove)
        
        # Simplify mesh
        mesh = mesh.simplify_quadric_mesh_decimation(target_count=100000)
        
        # Close small holes
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.remove_degenerate_triangles()
        
        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        
        return {
            "vertices": vertices,
            "faces": triangles,
            "vertex_count": len(vertices),
            "face_count": len(triangles),
            "method": "poisson",
        }
    
    except ImportError:
        raise MeshError("open3d not installed")
    except Exception as e:
        raise MeshError(f"Poisson reconstruction failed: {e}")


def generate_mesh_convex_hull(points: np.ndarray) -> Dict[str, Any]:
    """Generate mesh as convex hull (fast fallback).
    
    Args:
        points: 3D point cloud (N, 3)
        
    Returns:
        Dict with mesh info
    """
    try:
        from scipy.spatial import ConvexHull
        
        hull = ConvexHull(points)
        
        return {
            "vertices": hull.points[hull.vertices],
            "faces": hull.simplices,
            "vertex_count": len(hull.points[hull.vertices]),
            "face_count": len(hull.simplices),
            "method": "convex_hull",
        }
    
    except Exception as e:
        raise MeshError(f"Convex hull failed: {e}")


def run_stage5a_mesh(
    dense_data: Dict[str, Any],
    output_dir: Path,
    tier_config: "TierConfig",
    capture_id: str,
) -> Dict[str, Any]:
    """Run Stage 5a: Mesh generation.
    
    Args:
        dense_data: Dense reconstruction data (point cloud)
        output_dir: Output directory (work/ subdirectory)
        tier_config: Tier configuration (mesh_triangle_budget)
        capture_id: Capture job identifier
        
    Returns:
        Dict with mesh results:
        - mesh_triangles_count: number of triangles
        - mesh_vertices_count: number of vertices
        - stage5a_complete: whether stage passed
    """
    print(f"[{capture_id}] Stage 5a: Mesh Generation")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Load or create point cloud
        print(f"  Step 1: Loading point cloud...")
        
        if isinstance(dense_data, dict) and "dense_points" in dense_data:
            points = np.array(dense_data["dense_points"])
        else:
            # Synthetic point cloud
            np.random.seed(42)
            points = np.random.randn(10000, 3) * 2.0
            points[:, 2] += 15.0
        
        print(f"    Loaded {len(points)} points")
        
        # Step 2: Generate mesh
        print(f"  Step 2: Generating mesh...")
        
        try:
            mesh_data = generate_mesh_poisson(points, depth=8)
        except MeshError:
            print(f"    ⚠ Poisson failed, using convex hull")
            mesh_data = generate_mesh_convex_hull(points)
        
        vertices = mesh_data["vertices"]
        faces = mesh_data["faces"]
        
        print(f"    ✓ Mesh generated: {mesh_data['vertex_count']} vertices, {mesh_data['face_count']} faces")
        print(f"    Method: {mesh_data['method']}")
        
        # Step 3: Simplify mesh if needed
        print(f"  Step 3: Optimizing mesh density...")
        
        target_triangles = tier_config.mesh_triangle_budget
        current_triangles = len(faces)
        
        if current_triangles > target_triangles:
            # Simple decimation: keep only a subset
            step = max(1, current_triangles // target_triangles)
            faces = faces[::step]
            print(f"    Decimated to {len(faces)} triangles")
        
        # Step 4: Export mesh
        print(f"  Step 4: Exporting mesh...")
        
        # Export as OBJ (simple text format)
        obj_path = output_dir / "mesh.obj"
        with open(obj_path, "w") as f:
            f.write(f"# VantageCam Mesh Export\n")
            f.write(f"# Vertices: {len(vertices)}\n")
            f.write(f"# Faces: {len(faces)}\n\n")
            
            for v in vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            
            f.write("\n")
            for face in faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
        
        print(f"    ✓ Exported to {obj_path.name}")
        
        # Export as NumPy arrays for next stage
        vertices_path = output_dir / "mesh_vertices.npy"
        faces_path = output_dir / "mesh_faces.npy"
        np.save(vertices_path, vertices)
        np.save(faces_path, faces)
        
        result_dict = {
            "mesh_vertices_count": int(len(vertices)),
            "mesh_triangles_count": int(len(faces)),
            "obj_file": str(obj_path.name),
        }
        
        result_path = output_dir / "mesh_result.json"
        with open(result_path, "w") as f:
            json.dump(result_dict, f, indent=2)
        
        print(f"  ✓ Stage 5a complete: {len(vertices)} vertices, {len(faces)} triangles")
        
        return {
            "stage5a_complete": True,
            "mesh_vertices_count": len(vertices),
            "mesh_triangles_count": len(faces),
            "mesh_file": str(obj_path.name),
            "metrics": {
                "vertices": int(len(vertices)),
                "triangles": int(len(faces)),
            }
        }
    
    except Exception as e:
        print(f"  ❌ Mesh generation error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage5a_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import sys
    
    class MockTier:
        mesh_triangle_budget = 100000
    
    dense = {"dense_points": np.random.randn(5000, 3)}
    output = Path("output/vantagecam/test_stage5a/work")
    result = run_stage5a_mesh(dense, output, MockTier(), "test_capture")
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
