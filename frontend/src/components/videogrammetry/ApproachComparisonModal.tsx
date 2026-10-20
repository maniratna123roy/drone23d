import React from "react";
import { X, CheckCircle2, Info, Sparkles, Box } from "lucide-react";

interface ApproachComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ApproachComparisonModal: React.FC<ApproachComparisonModalProps> = ({
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-card p-6 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-6">
          <div className="flex items-center gap-2 text-xs font-mono uppercase text-purple-400 mb-1">
            <Sparkles className="h-4 w-4" /> Architectural Comparison
          </div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">
            Gaussian Splatting vs Videogrammetry (Skyebrowse Model)
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            How the two parallel 3D reconstruction systems differ in mathematics, outputs, and operational tradeoffs.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="p-3 font-semibold text-muted-foreground">Dimension</th>
                <th className="p-3 font-semibold text-cyan-400">
                  Approach A: 3D Gaussian Splatting (Current Host)
                </th>
                <th className="p-3 font-semibold text-purple-400">
                  Approach B: Videogrammetry Sidecar (Skyebrowse Model)
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Primary Primitive</td>
                <td className="p-3 text-muted-foreground">
                  3D ellipsoidal Gaussian splats (position, covariance, opacity, spherical harmonics)
                </td>
                <td className="p-3 text-muted-foreground">
                  Triangular polygon mesh (vertices, faces, texture atlas) + Metric point cloud (LAZ)
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Mathematical Core</td>
                <td className="p-3 text-muted-foreground">
                  Gradient-based per-scene radiance field optimization (gsplat)
                </td>
                <td className="p-3 text-muted-foreground">
                  Sequential SfM (COLMAP/GLOMAP) + Multi-View Stereo (MVS) + Poisson Surface Meshing
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Input Data</td>
                <td className="p-3 text-muted-foreground">
                  Pre-calibrated multi-view drone images + camera poses
                </td>
                <td className="p-3 text-muted-foreground">
                  Single continuous video file + optional companion DJI SRT/GPS telemetry
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">CAD & GIS Interoperability</td>
                <td className="p-3 text-muted-foreground">
                  Challenging; splats lack discrete surface topology (requires proxy meshes)
                </td>
                <td className="p-3 text-muted-foreground">
                  Native; produces standard GLB, Wavefront OBJ, Cloud-Optimized GeoTIFF, and LAZ
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Quality Assurance Loop</td>
                <td className="p-3 text-muted-foreground">
                  Manual inspection of PSNR / SSIM loss curve
                </td>
                <td className="p-3 text-muted-foreground">
                  Automated AI Quality Gate with 3-step retry ladder (widened window, masking, higher res)
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Moving Objects (Vehicles/People)</td>
                <td className="p-3 text-muted-foreground">
                  Appear as "floaters" or blurred artifacts unless explicitly masked out
                </td>
                <td className="p-3 text-muted-foreground">
                  Dynamic-object instance masking eliminates non-stationary pixels before matching
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Resolution Tiers</td>
                <td className="p-3 text-muted-foreground">
                  Single iteration budget (~15,000–30,000 optimization steps)
                </td>
                <td className="p-3 text-muted-foreground">
                  4 Configurable Tiers: Lite (1080p), Standard (4K), Premium (4K-8K), Premium Advanced (8K tiled)
                </td>
              </tr>
              <tr>
                <td className="p-3 font-mono font-medium text-foreground">Rendering in Browser</td>
                <td className="p-3 text-muted-foreground">
                  Custom WebGL / WebGPU rasterizer (gsplat.js)
                </td>
                <td className="p-3 text-muted-foreground">
                  Standard Three.js PBR Mesh rendering (zero special shaders required)
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="rounded bg-primary px-4 py-2 font-mono text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Close Comparison
          </button>
        </div>
      </div>
    </div>
  );
};
