"""Phase C: fit actual 3D Gaussians to verified Phase B photographs.

Analogy: adjust tiny colored lenses until their images match the photographs.
No procedural surfaces, synthetic scene fallback, inferred class labels, or
unmeasured 'facade verified' claims. Scene coordinates remain COLMAP-relative.
"""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint

from pipeline.colmap_reconstructor import parse_colmap_reconstruction, read_dense_ply
from pipeline.dense_reconstruction import read_colmap_depth
from pipeline.common.io import save_splat, save_classes, save_ply


def build_rotation(q):
    q = F.normalize(q, dim=1, eps=1e-8)
    w, x, y, z = q.unbind(1)
    return torch.stack((1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y),
                        2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x),
                        2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)), dim=1).reshape(-1, 3, 3)


def build_covariance_3d(scales, rotations):
    matrix = build_rotation(rotations) * scales.unsqueeze(1)
    return matrix @ matrix.transpose(1, 2)


def project_gaussians(means3d, scales, rotations, R_cw, t_cw, fx, fy, cx, cy, W, H):
    camera = means3d @ R_cw.T + t_cw
    # Cull BEFORE division: zero-depth points must not create NaN gradients.
    indices = torch.where(torch.isfinite(camera).all(dim=1) & (camera[:, 2] > 1e-4))[0]
    if not len(indices):
        return None
    camera = camera[indices]
    x, y, z = camera.unbind(1)
    u, v = fx*x/z + cx, fy*y/z + cy
    zero = torch.zeros_like(z)
    # EWA linearization is invalid arbitrarily far off-axis. Bound the
    # Jacobian to a 1.3x field-of-view margin, as in Gaussian rasterizers;
    # leave projected means unchanged so off-screen centers are still culled.
    x_over_z = (x/z).clamp(-1.3*W/(2*fx), 1.3*W/(2*fx))
    y_over_z = (y/z).clamp(-1.3*H/(2*fy), 1.3*H/(2*fy))
    jacobian = torch.stack((fx/z, zero, -fx*x_over_z/z, zero, fy/z, -fy*y_over_z/z), dim=1).reshape(-1, 2, 3)
    covariance = build_covariance_3d(scales[indices], rotations[indices])
    camera_cov = R_cw.unsqueeze(0) @ covariance @ R_cw.T.unsqueeze(0)
    screen_cov = jacobian @ camera_cov @ jacobian.transpose(1, 2)
    screen_cov = screen_cov + torch.eye(2, device=z.device, dtype=z.dtype).unsqueeze(0)*0.3
    a, b, c = screen_cov[:, 0, 0], screen_cov[:, 0, 1], screen_cov[:, 1, 1]
    determinant = (a*c - b*b).clamp_min(1e-10)
    inverse = torch.stack((c, -b, -b, a), dim=1).reshape(-1, 2, 2) / determinant[:, None, None]
    # Radius is for discrete tile assignment; covariance still carries gradients.
    with torch.no_grad():
        largest = 0.5*(a+c) + torch.sqrt((0.25*(a-c).square() + b.square()).clamp_min(0))
        radius = torch.ceil(3*torch.sqrt(largest.clamp_min(1e-8)))
        visible = (u+radius >= 0) & (u-radius < W) & (v+radius >= 0) & (v-radius < H)
    if not visible.any():
        return None
    return {"indices": indices[visible], "u": u[visible], "v": v[visible], "z": z[visible],
            "inv_cov2d": inverse[visible], "radius": radius[visible]}


def _composite_tile(means, colors, opacity, inverse, pixels, background):
    """Exact ordered compositing over ALL candidates, in bounded chunks."""
    result = torch.zeros((len(pixels), 3), device=means.device, dtype=means.dtype)
    transmittance = torch.ones((len(pixels), 1), device=means.device, dtype=means.dtype)
    for start in range(0, len(means), 256):
        end = start + 256
        delta = pixels[:, None, :] - means[None, start:end, :]
        inv = inverse[start:end]
        power = -0.5*(inv[None, :, 0, 0]*delta[..., 0].square()
                      + 2*inv[None, :, 0, 1]*delta[..., 0]*delta[..., 1]
                      + inv[None, :, 1, 1]*delta[..., 1].square())
        alpha = (opacity[None, start:end]*torch.exp(power.clamp(max=0))).clamp(max=0.99)
        alpha = torch.where(power >= -4.5, alpha, torch.zeros_like(alpha))
        cumulative = torch.cumprod(1-alpha, dim=1)
        before = torch.cat((torch.ones_like(cumulative[:, :1]), cumulative[:, :-1]), dim=1)
        result = result + transmittance * ((alpha*before) @ colors[start:end])
        transmittance = transmittance * cumulative[:, -1:]
    return result + transmittance*background


def _composite_tile_batch(means, colors, opacity, inverse, pixels, background):
    """Same ordered alpha equation as _composite_tile, across eight tiles."""
    batch, pixel_count = pixels.shape[:2]
    result = torch.zeros((batch, pixel_count, 3), device=means.device, dtype=means.dtype)
    transmittance = torch.ones((batch, pixel_count, 1), device=means.device, dtype=means.dtype)
    for start in range(0, means.shape[1], 256):
        end = start+256
        delta = pixels[:, :, None, :] - means[:, None, start:end, :]
        inv = inverse[:, start:end]
        power = -0.5*(inv[:, None, :, 0, 0]*delta[..., 0].square()
                      + 2*inv[:, None, :, 0, 1]*delta[..., 0]*delta[..., 1]
                      + inv[:, None, :, 1, 1]*delta[..., 1].square())
        alpha = (opacity[:, None, start:end]*torch.exp(power.clamp(max=0))).clamp(max=0.99)
        alpha = torch.where(power >= -4.5, alpha, torch.zeros_like(alpha))
        cumulative = torch.cumprod(1-alpha, dim=2)
        before = torch.cat((torch.ones_like(cumulative[:, :, :1]), cumulative[:, :, :-1]), dim=2)
        result = result + transmittance*torch.bmm(alpha*before, colors[:, start:end])
        transmittance = transmittance*cumulative[:, :, -1:]
    return result + transmittance*background


def rasterize_tiles(means2d, depths, colors, opacities, inv_cov2d, radii, H, W,
                    tile_size=16, bg_color=None):
    if H <= 0 or W <= 0 or tile_size <= 0:
        raise ValueError("Render dimensions and tile size must be positive")
    if bg_color is None:
        bg_color = torch.zeros(3, device=means2d.device, dtype=means2d.dtype)
    if not len(means2d):
        return bg_color.expand(H, W, 3)
    order = torch.argsort(depths)
    means, colors, opacity = means2d[order], colors[order], opacities[order]
    inverse, radii = inv_cov2d[order], radii[order]
    bounds = torch.cat((means.detach(), radii.detach()[:, None]), dim=1).cpu().numpy()
    origins, candidates = [], []
    for y0 in range(0, H, tile_size):
        for x0 in range(0, W, tile_size):
            overlap = ((bounds[:, 0]+bounds[:, 2] >= x0) & (bounds[:, 0]-bounds[:, 2] < x0+tile_size)
                       & (bounds[:, 1]+bounds[:, 2] >= y0) & (bounds[:, 1]-bounds[:, 2] < y0+tile_size))
            origins.append((x0, y0))
            candidates.append(np.flatnonzero(overlap))
    yy, xx = torch.meshgrid(torch.arange(tile_size, device=means.device, dtype=means.dtype),
                            torch.arange(tile_size, device=means.device, dtype=means.dtype), indexing="ij")
    local_pixels = torch.stack((xx.flatten(), yy.flatten()), dim=1)
    rendered_tiles = []
    for start in range(0, len(origins), 8):
        group = candidates[start:start+8]
        count = max(map(len, group))
        if count == 0:
            rendered_tiles.append(bg_color.expand(len(group), tile_size*tile_size, 3))
            continue
        indices = np.zeros((len(group), count), dtype=np.int64)
        active = np.zeros_like(indices, dtype=np.float32)
        for index, values in enumerate(group):
            indices[index, :len(values)] = values
            active[index, :len(values)] = 1
        ids = torch.as_tensor(indices, device=means.device)
        valid = torch.as_tensor(active, device=means.device)
        offsets = torch.tensor(origins[start:start+8], device=means.device, dtype=means.dtype)
        pixels = local_pixels[None] + offsets[:, None]
        args = (means[ids], colors[ids], opacity[ids]*valid, inverse[ids], pixels, bg_color)
        if torch.is_grad_enabled() and any(value.requires_grad for value in args):
            tile = checkpoint(_composite_tile_batch, *args, use_reentrant=False)
        else:
            tile = _composite_tile_batch(*args)
        rendered_tiles.append(tile)
    tiles = torch.cat(rendered_tiles, dim=0)
    ny, nx = (H+tile_size-1)//tile_size, (W+tile_size-1)//tile_size
    image = tiles.reshape(ny, nx, tile_size, tile_size, 3).permute(0, 2, 1, 3, 4)
    return image.reshape(ny*tile_size, nx*tile_size, 3)[:H, :W]


def create_ssim_window(window_size=11, channel=3, device="cuda"):
    coords = torch.arange(window_size, dtype=torch.float32, device=device) - window_size//2
    weights = torch.exp(-coords.square()/(2*1.5**2))
    weights /= weights.sum()
    return (weights[:, None]*weights[None, :])[None, None].repeat(channel, 1, 1, 1)


def _ssim_map(first, second, window):
    padding, channels = window.shape[-1]//2, first.shape[1]
    conv = lambda image: F.conv2d(image, window, padding=padding, groups=channels)
    mu1, mu2 = conv(first), conv(second)
    var1, var2 = conv(first*first)-mu1.square(), conv(second*second)-mu2.square()
    covariance = conv(first*second)-mu1*mu2
    return ((2*mu1*mu2+0.01**2)*(2*covariance+0.03**2) /
            ((mu1.square()+mu2.square()+0.01**2)*(var1+var2+0.03**2)))


def ssim_loss(img1, img2, window):
    return 1-_ssim_map(img1, img2, window).mean()


def photometric_loss(rendered, target, support, window):
    if not support.any():
        raise ValueError("No measured surface support for photometric loss")
    l1 = (rendered[support]-target[support]).abs().mean()
    # Fixed MVS support, never a mask selected from the model's own alpha.
    masked_render = rendered * support[..., None]
    masked_target = target * support[..., None]
    similarity = _ssim_map(masked_render.permute(2, 0, 1)[None],
                           masked_target.permute(2, 0, 1)[None], window).mean(dim=1)[0]
    structural = 1-similarity[support].mean()
    return 0.8*l1 + 0.2*structural, l1, structural


class GaussianModel(nn.Module):
    def __init__(self, init_positions, init_colors, device, init_normals=None):
        super().__init__()
        points = np.asarray(init_positions, dtype=np.float32)
        colors = np.asarray(init_colors)
        if points.ndim != 2 or points.shape[1] != 3 or not len(points) or not np.isfinite(points).all():
            raise ValueError("Gaussian initialization needs nonempty finite Nx3 positions")
        if colors.shape not in ((len(points), 3), (len(points), 4)) or not np.isfinite(colors).all() or (colors < 0).any() or (colors > 255).any():
            raise ValueError("Gaussian initialization needs matching RGB values in [0,255]")
        if len(points) == 1:
            spacing = np.array([0.01], np.float32)
        else:
            distances, _ = cKDTree(points).query(points, k=min(4, len(points)))
            spacing = np.sqrt(np.mean(distances[:, 1:]**2, axis=1)).astype(np.float32)
            spacing = np.maximum(spacing, 1e-5)
            # Isolated MVS outliers must not initialize scene-sized ellipsoids.
            # This changes kernel extent, never the measured point coordinates.
            spacing = np.minimum(spacing, np.percentile(spacing, 95))
        scales = np.column_stack((spacing, spacing, spacing*0.3))
        rotations = np.zeros((len(points), 4), np.float32)
        rotations[:, 0] = 1
        if init_normals is not None:
            normals = np.asarray(init_normals, dtype=np.float32)
            if normals.shape != points.shape or not np.isfinite(normals).all() or (np.linalg.norm(normals, axis=1) < 1e-8).any():
                raise ValueError("Expected finite nonzero MVS normals")
            normals = normals / np.linalg.norm(normals, axis=1, keepdims=True)
            rotations = np.column_stack((1+normals[:, 2], -normals[:, 1], normals[:, 0], np.zeros(len(points))))
            antipodal = np.linalg.norm(rotations, axis=1) < 1e-6
            rotations[antipodal] = [0, 1, 0, 0]
            rotations /= np.linalg.norm(rotations, axis=1, keepdims=True)
        tensor = lambda value: torch.as_tensor(value, device=device, dtype=torch.float32)
        self._xyz = nn.Parameter(tensor(points.copy()))
        self._scaling = nn.Parameter(tensor(np.log(scales)))
        self._rotation = nn.Parameter(tensor(rotations))
        self._opacity = nn.Parameter(torch.full((len(points), 1), 0.85, device=device))
        color = np.clip(colors[:, :3].astype(np.float32)/255, 1e-4, 1-1e-4)
        self._features_dc = nn.Parameter(tensor(np.log(color/(1-color))))
        self.register_buffer("anchor_xyz", tensor(points.copy()))
        self.register_buffer("anchor_scales", tensor(scales))
        self.register_buffer("source_indices", torch.arange(len(points), device=device))

    def get_xyz(self):
        return self._xyz

    def get_scaling(self):
        return self._scaling.exp()

    def get_rotation(self):
        return F.normalize(self._rotation, dim=1, eps=1e-8)

    def get_opacity(self):
        return self._opacity.sigmoid().squeeze(-1)

    def get_features(self):
        return self._features_dc.sigmoid()

    def setup_optimizers(self):
        xyz_lr = 0.05*float(self.anchor_scales[:, 0].median())
        rates = {"_xyz": xyz_lr, "_features_dc": 0.01, "_opacity": 0.025,
                 "_scaling": 0.005, "_rotation": 0.002}
        return torch.optim.Adam([{"params": [value], "lr": rates[name], "name": name}
                                 for name, value in self.named_parameters()], eps=1e-8)

    @torch.no_grad()
    def constrain_to_observations(self):
        # Bounded refinement near measured surfaces; never seed unseen walls.
        offset = self._xyz-self.anchor_xyz
        limit = 2*self.anchor_scales[:, :1]
        self._xyz.copy_(self.anchor_xyz + offset*(limit/offset.norm(dim=1, keepdim=True).clamp_min(1e-10)).clamp(max=1))
        self._scaling.copy_(torch.maximum(torch.minimum(self._scaling, (self.anchor_scales*4).log()),
                                         (self.anchor_scales*0.25).log()))
        self._rotation.copy_(self.get_rotation())
        self._opacity.clamp_(-12, 12)
        self._features_dc.clamp_(-12, 12)

    def prune_gaussians(self, min_opacity=0.05, max_scale=float("inf")):
        with torch.no_grad():
            keep = (self.get_opacity() >= min_opacity) & (self.get_scaling().amax(dim=1) <= max_scale)
            if not keep.any():
                raise ValueError("Pruning would remove all Gaussians; model is not valid")
            for name, value in list(self.named_parameters()):
                setattr(self, name, nn.Parameter(value[keep].detach().clone()))
            self.anchor_xyz = self.anchor_xyz[keep]
            self.anchor_scales = self.anchor_scales[keep]
            self.source_indices = self.source_indices[keep]


def split_view_names(names):
    names = sorted(names)
    if len(names) < 5 or len(set(names)) != len(names):
        raise ValueError("Phase C requires at least five distinct registered views")
    validation = [name for index, name in enumerate(names) if index % 5 == 4]
    return [name for name in names if name not in validation], validation


def load_phase_b_inputs(workspace):
    root = Path(workspace).resolve()
    report = json.loads((root/"dense_quality_report.json").read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("status") != "PASSED" or report.get("source") != "COLMAP_GEOMETRIC_MVS":
        raise ValueError("Phase B must have a passed geometric-MVS report; no fallback cloud is allowed")
    if report.get("coordinate_frame") != "COLMAP_PHASE_A" or report.get("neural_depth_run") or report.get("procedural_fallback_run"):
        raise ValueError("Phase B frame/provenance is incompatible with strict Phase C")
    cloud = root/"verified_dense.ply"
    positions, colors, normals = read_dense_ply(cloud)
    if len(positions) != report.get("retained_points") or not len(positions):
        raise ValueError("Phase B point count does not match its verification report")
    if not np.isfinite(positions).all() or not np.isfinite(normals).all() or (np.linalg.norm(normals, axis=1) < 1e-8).any():
        raise ValueError("Phase B contains invalid geometry/normals")
    cameras_path = root/"undistorted_sparse_txt"
    poses, cameras, _, _ = parse_colmap_reconstruction(cameras_path)
    if set(poses) != set(report["phase_a_recheck"]["registered_image_names"]):
        raise ValueError("Phase B camera set changed since verification")
    fingerprints = {"verified_dense.ply": hashlib.sha256(cloud.read_bytes()).hexdigest()}
    for path in sorted(cameras_path.glob("*.txt")):
        fingerprints[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name, pose in poses.items():
        camera = cameras[pose["camera_id"]]
        if camera["model"] not in {"PINHOLE", "SIMPLE_PINHOLE"} or min(camera["fx"], camera["fy"]) <= 0:
            raise ValueError("Use the matching undistorted pinhole cameras from Phase B")
        image = root/"dense/images"/name
        depth = root/"dense/stereo/depth_maps"/f"{name}.geometric.bin"
        if not image.resolve().is_relative_to(root) or not depth.resolve().is_relative_to(root):
            raise ValueError("Invalid camera image path")
        for path in (image, depth):
            fingerprints[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        with Image.open(image) as photo:
            if photo.size != (camera["width"], camera["height"]):
                raise ValueError(f"Image/camera dimensions differ: {name}")
    return {"root": root, "report": report, "positions": positions, "colors": colors,
            "normals": normals, "poses": poses, "cameras": cameras, "sha256": fingerprints}


def prepare_views(data, width, device):
    views = []
    for name, pose in sorted(data["poses"].items()):
        camera = data["cameras"][pose["camera_id"]]
        height = max(1, round(camera["height"]*width/camera["width"]))
        with Image.open(data["root"]/"dense/images"/name) as photo:
            image = np.array(photo.convert("RGB").resize((width, height), Image.Resampling.LANCZOS))
        depth = read_colmap_depth(data["root"]/"dense/stereo/depth_maps"/f"{name}.geometric.bin")
        support = np.isfinite(depth) & (depth > 0)
        support = np.array(Image.fromarray(support).resize((width, height), Image.Resampling.NEAREST))
        if support.sum() < 50:
            raise ValueError(f"Insufficient measured surface support: {name}")
        views.append({"name": name, "width": width, "height": height,
                      "target": torch.tensor(image, device=device, dtype=torch.float32)/255,
                      "support": torch.tensor(support, device=device, dtype=torch.bool),
                      "R_cw": torch.tensor(pose["R_cw"], device=device, dtype=torch.float32),
                      "t_cw": torch.tensor(pose["t_cw"], device=device, dtype=torch.float32),
                      "fx": camera["fx"]*width/camera["width"], "fy": camera["fy"]*height/camera["height"],
                      "cx": camera["cx"]*width/camera["width"], "cy": camera["cy"]*height/camera["height"]})
    return views


def render_view(model, view):
    projection = project_gaussians(model.get_xyz(), model.get_scaling(), model.get_rotation(), view["R_cw"], view["t_cw"],
                                   view["fx"], view["fy"], view["cx"], view["cy"], view["width"], view["height"])
    if projection is None:
        raise ValueError(f"No visible Gaussians for {view['name']}; cannot silently skip the view")
    ids = projection["indices"]
    return rasterize_tiles(torch.stack((projection["u"], projection["v"]), dim=1), projection["z"],
                            model.get_features()[ids], model.get_opacity()[ids], projection["inv_cov2d"],
                            projection["radius"], view["height"], view["width"])


@torch.no_grad()
def evaluate_views(model, views, window, output_dir=None):
    per_view = []
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    for view in views:
        rendered = render_view(model, view)
        if not torch.isfinite(rendered).all():
            raise ValueError("Nonfinite rendered image")
        target, support = view["target"], view["support"]
        _, l1, structural = photometric_loss(rendered, target, support, window)
        surface_mse = (rendered[support]-target[support]).square().mean().item()
        full_mse = (rendered-target).square().mean().item()
        per_view.append({"name": view["name"], "surface_psnr_db": -10*math.log10(max(surface_mse, 1e-12)),
                         "surface_ssim": 1-float(structural), "surface_l1": float(l1),
                         "full_frame_psnr_db": -10*math.log10(max(full_mse, 1e-12)),
                         "support_fraction": float(support.float().mean())})
        if output_dir is not None:
            original = (target.cpu().numpy()*255).round().clip(0, 255).astype(np.uint8)
            result = (rendered.cpu().numpy()*255).round().clip(0, 255).astype(np.uint8)
            error = np.abs(original.astype(float)-result).mean(axis=2)
            heat = np.zeros_like(original)
            heat[..., 0] = np.clip(error*3, 0, 255).astype(np.uint8)
            mask = np.repeat(support.cpu().numpy()[..., None]*255, 3, axis=2).astype(np.uint8)
            panels = Image.fromarray(np.hstack((original, result, heat, mask)))
            canvas = Image.new("RGB", (panels.width, panels.height+22))
            canvas.paste(panels, (0, 22))
            draw = ImageDraw.Draw(canvas)
            for index, title in enumerate(("Real photograph", "Gaussian render", "Absolute error", "Fixed MVS support")):
                draw.text((index*view["width"]+3, 4), title, fill="white")
            canvas.save(output_dir/f"{Path(view['name']).stem}.png")
    if not per_view:
        raise ValueError("No evaluation views")
    mean = {key: float(np.mean([entry[key] for entry in per_view])) for key in per_view[0] if key != "name"}
    return {**mean, "views": per_view}


def evaluate_quality_gate(baseline, final, steps, finite_parameters):
    required = ("surface_psnr_db", "surface_ssim", "surface_l1")
    finite = all(math.isfinite(metrics[key]) for metrics in (baseline, final) for key in required)
    checks = {"finite_training": bool(finite_parameters and finite and steps > 0),
              "heldout_improvement": bool(finite and final["surface_psnr_db"] >= baseline["surface_psnr_db"]+0.25
                                          and final["surface_l1"] <= baseline["surface_l1"]*0.95),
              "heldout_surface_psnr": bool(finite and final["surface_psnr_db"] >= 20),
              "heldout_surface_ssim": bool(finite and final["surface_ssim"] >= 0.60)}
    failed = [name for name, passed in checks.items() if not passed]
    return {"status": "FAILED" if failed else "PASSED", "checks": checks, "failed_checks": failed,
            "thresholds": {"min_surface_psnr_db": 20, "min_surface_ssim": 0.60,
                           "min_psnr_gain_db": 0.25, "min_l1_reduction_fraction": 0.05}}


def train_3dgs(model, training_views, window, iterations, output_dir):
    optimizer = model.setup_optimizers()
    history, gradient_evidence = [], {}
    started = time.perf_counter()
    with (output_dir/"training.jsonl").open("w", encoding="utf-8") as log:
        for step in range(1, iterations+1):
            view = training_views[(step-1) % len(training_views)]
            optimizer.zero_grad(set_to_none=True)
            rendered = render_view(model, view)
            photometric, l1, structural = photometric_loss(rendered, view["target"], view["support"], window)
            anchor_loss = ((model._xyz-model.anchor_xyz)/model.anchor_scales[:, :1]).square().mean()
            loss = photometric + 0.001*anchor_loss
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite photometric loss; training aborted")
            loss.backward()
            for name, parameter in model.named_parameters():
                if parameter.grad is None or not torch.isfinite(parameter.grad).all():
                    raise ValueError(f"Missing/nonfinite gradient for {name}")
                if step <= len(training_views) or step % 50 == 0:
                    gradient_evidence[name] = max(gradient_evidence.get(name, 0.), float(parameter.grad.abs().max()))
            optimizer.step()
            model.constrain_to_observations()
            row = {"step": step, "view": view["name"], "loss": float(loss.detach()),
                   "photometric_loss": float(photometric.detach()), "surface_l1": float(l1.detach()),
                   "surface_ssim": 1-float(structural.detach()), "anchor_loss": float(anchor_loss.detach()),
                   "elapsed_seconds": round(time.perf_counter()-started, 2)}
            history.append(row)
            log.write(json.dumps(row)+"\n")
            if step == 1 or step % 25 == 0 or step == iterations:
                log.flush()
                print(f"[3DGS {step}/{iterations}] loss={row['loss']:.5f} L1={row['surface_l1']:.5f} SSIM={row['surface_ssim']:.3f} elapsed={row['elapsed_seconds']}s", flush=True)
    return history, gradient_evidence


def decode_splat(path, device):
    dtype = np.dtype([("xyz", "<f4", (3,)), ("scales", "<f4", (3,)), ("rgba", "u1", (4,)), ("q", "u1", (4,))])
    if Path(path).stat().st_size % 32:
        raise ValueError("Invalid binary splat byte count")
    records = np.fromfile(path, dtype=dtype)
    model = GaussianModel(records["xyz"].copy(), records["rgba"][:, :3].copy(), device)
    with torch.no_grad():
        model._scaling.copy_(torch.as_tensor(np.log(records["scales"]), device=device))
        q = (records["q"].astype(np.float32)-128)/128
        model._rotation.copy_(F.normalize(torch.as_tensor(q, device=device), dim=1))
        alpha = np.clip(records["rgba"][:, 3].astype(np.float32)/255, 1e-6, 1-1e-6)
        model._opacity.copy_(torch.as_tensor(np.log(alpha/(1-alpha))[:, None], device=device))
    return model


def load_gaussian_checkpoint(path, device):
    """Reload tensor-only training state, without enabling arbitrary pickle objects."""
    saved = torch.load(path, map_location=device, weights_only=True)
    state = saved["model"]
    colors = (state["_features_dc"].sigmoid().detach().cpu().numpy()*255).round().astype(np.uint8)
    model = GaussianModel(state["_xyz"].detach().cpu().numpy(), colors, device)
    model.load_state_dict(state, strict=True)
    if not all(bool(torch.isfinite(value).all()) for value in model.parameters()):
        raise ValueError("Checkpoint contains nonfinite Gaussian parameters")
    return model


def export_optimized_web_splat(model, output_dir):
    """Export in the SAME frame; missing semantics are UNKNOWN (255), not buildings."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with torch.no_grad():
        xyz = model.get_xyz().cpu().numpy()
        scales = model.get_scaling().cpu().numpy()
        rotations = model.get_rotation().cpu().numpy()
        rgb = (model.get_features().cpu().numpy()*255).round().clip(0, 255).astype(np.uint8)
        alpha = model.get_opacity().cpu().numpy()
    rgba = np.column_stack((rgb, (alpha*255).round().clip(0, 255).astype(np.uint8)))
    save_splat(xyz, scales, rotations, rgba, str(output_dir/"scene.splat"))
    save_classes(np.full(len(xyz), 255, dtype=np.uint8), str(output_dir/"scene.classes.u8"))
    save_ply(str(output_dir/"optimized_gaussians.ply"), xyz, rgb, scales, rotations, alpha)
    if (output_dir/"scene.splat").stat().st_size != 32*len(xyz) or (output_dir/"scene.classes.u8").stat().st_size != len(xyz):
        raise ValueError("Splat/sidecar order-count contract failed")
    return {"count": len(xyz), "coordinate_frame": "COLMAP_PHASE_A", "scale_status": "RELATIVE_UNCALIBRATED",
            "class_status": "UNKNOWN_255_NOT_INFERRED", "ground_alignment_applied": False,
            "splat_file": str(output_dir/"scene.splat"), "scene_published": False}


def execute_phase_c_3dgs_pipeline(phase_b_workspace, output_dir, iterations=1000,
                                  render_width=320, max_gaussians=40000, device="cuda", seed=42):
    if iterations <= 0 or not 32 <= render_width <= 1024 or max_gaussians < 1:
        raise ValueError("Use positive iterations/Gaussian count and render width 32..1024")
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Phase C requires a fresh output workspace; existing results are protected")
    dev = torch.device(device)
    if dev.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable; explicitly choose --device cpu or fix the GPU runtime")
    torch.manual_seed(seed)
    np.random.seed(seed)
    data = load_phase_b_inputs(phase_b_workspace)
    output.mkdir(parents=True, exist_ok=True)
    report = {"phase": "C", "status": "FAILED", "phase_b_workspace": str(data["root"]), "input_sha256": data["sha256"],
              "seed": seed, "device": str(dev), "render_width": render_width, "requested_iterations": iterations,
              "coordinate_frame": "COLMAP_PHASE_A", "scale_status": "RELATIVE_UNCALIBRATED",
              "mock_scene_used": False, "procedural_fallback_run": False, "scene_published": False,
              "validation_scope": "Views withheld from Gaussian gradients ONLY; SfM/MVS used all input views. Not unseen-scene accuracy.",
              "surface_mask_source": "Fixed positive finite COLMAP geometric depth; independent of rendered opacity",
              "geometry_constraints": "Initial spacing capped at observed 95th percentile; centers within 2 initial spacings of measured points; scales within 0.25..4x initial scales; no new surfaces seeded"}
    report_path = output/"phase_c_report.json"
    try:
        if dev.type == "cuda":
            torch.cuda.reset_peak_memory_stats(dev)
        views = prepare_views(data, render_width, dev)
        train_names, heldout_names = split_view_names([view["name"] for view in views])
        training = [view for view in views if view["name"] in train_names]
        heldout = [view for view in views if view["name"] in heldout_names]
        report.update(training_views=train_names, heldout_views=heldout_names)
        chosen = np.arange(len(data["positions"]))
        if len(chosen) > max_gaussians:
            chosen = np.sort(np.random.default_rng(seed).choice(chosen, max_gaussians, replace=False))
        model = GaussianModel(data["positions"][chosen], data["colors"][chosen], dev, data["normals"][chosen])
        initial = {name: value.detach().cpu().clone() for name, value in model.named_parameters()}
        window = create_ssim_window(11, 3, str(dev))
        print(f"[PHASE C] Real MVS points={len(data['positions'])}; initialized Gaussians={len(chosen)}; train/heldout={len(training)}/{len(heldout)}", flush=True)
        baseline_training = evaluate_views(model, training, window)
        baseline_heldout = evaluate_views(model, heldout, window, output/"baseline_heldout")
        report["baseline"] = {"training": baseline_training, "heldout": baseline_heldout}
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(f"[BASELINE] heldout surface PSNR={baseline_heldout['surface_psnr_db']:.2f} SSIM={baseline_heldout['surface_ssim']:.3f}", flush=True)
        history, gradients = train_3dgs(model, training, window, iterations, output)
        before_prune = len(model.get_xyz())
        model.prune_gaussians(min_opacity=0.02)
        final_training = evaluate_views(model, training, window, output/"final_training")
        final_heldout = evaluate_views(model, heldout, window, output/"final_heldout")
        finite = all(bool(torch.isfinite(value).all()) for value in model.parameters())
        gate = evaluate_quality_gate(baseline_heldout, final_heldout, len(history), finite)
        deltas = {name: float((value.detach().cpu()-initial[name][model.source_indices.cpu()]).abs().mean())
                  for name, value in model.named_parameters()}
        gradient_pass = all(value > 0 for value in gradients.values()) and len(gradients) == 5 and all(value > 0 for value in deltas.values())
        gate["checks"]["all_parameter_groups_optimized"] = gradient_pass
        if not gradient_pass:
            gate["failed_checks"].append("all_parameter_groups_optimized")
            gate["status"] = "FAILED"
        torch.save({"model": model.state_dict(), "config": {"seed": seed, "render_width": render_width},
                    "training_views": train_names, "heldout_views": heldout_names,
                    "phase_b_point_indices": torch.from_numpy(chosen[model.source_indices.cpu().numpy()])}, output/"model.pt")
        restored = load_gaussian_checkpoint(output/"model.pt", dev)
        report["checkpoint_roundtrip_exact"] = all(torch.equal(value, restored.state_dict()[name])
                                                    for name, value in model.state_dict().items())
        del restored
        if not report["checkpoint_roundtrip_exact"]:
            raise ValueError("Checkpoint round trip changed learned parameters")
        report.update(status=gate["status"], quality_gate=gate, final={"training": final_training, "heldout": final_heldout},
                      completed_steps=len(history), initial_gaussians=before_prune, final_gaussians=len(model.get_xyz()),
                      gradient_max_abs=gradients, parameter_mean_absolute_changes=deltas)
        if dev.type == "cuda":
            report["torch_peak_allocated_mb"] = torch.cuda.max_memory_allocated(dev)/(1024**2)
            report["torch_peak_reserved_mb"] = torch.cuda.max_memory_reserved(dev)/(1024**2)
        if gate["status"] == "PASSED":
            assets = output/"assets"
            report["export"] = export_optimized_web_splat(model, assets)
            decoded = decode_splat(assets/"scene.splat", dev)
            exported_metrics = evaluate_views(decoded, heldout, window, output/"exported_heldout")
            psnr_delta = abs(exported_metrics["surface_psnr_db"]-final_heldout["surface_psnr_db"])
            ssim_delta = abs(exported_metrics["surface_ssim"]-final_heldout["surface_ssim"])
            report["export_roundtrip"] = {"metrics": exported_metrics, "psnr_delta_db": psnr_delta, "ssim_delta": ssim_delta,
                                           "passed": psnr_delta <= 0.5 and ssim_delta <= 0.02}
            if not report["export_roundtrip"]["passed"]:
                report["status"] = "FAILED"
                (assets/"scene.splat").unlink()
                (assets/"scene.classes.u8").unlink()
                report["export"]["status"] = "REJECTED_ROUNDTRIP"
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(f"[PHASE C] {report['status']}; heldout surface PSNR {baseline_heldout['surface_psnr_db']:.2f} -> {final_heldout['surface_psnr_db']:.2f}; SSIM {final_heldout['surface_ssim']:.3f}", flush=True)
        return report
    except Exception as exc:
        report.update(status="FAILED", error=str(exc))
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Strict Phase C: fit real Phase B images; no mock fallback")
    parser.add_argument("--phase-b-workspace", required=True)
    parser.add_argument("--output", required=True, help="Fresh isolated workspace; never the live static directory")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--render-width", type=int, default=320)
    parser.add_argument("--max-gaussians", type=int, default=40000)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        result = execute_phase_c_3dgs_pipeline(args.phase_b_workspace, args.output, args.iterations,
                                              args.render_width, args.max_gaussians, args.device, args.seed)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"[PHASE C ERROR] {exc}\nNo mock geometry or live scene replacement was used.", file=sys.stderr)
        return 1
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
