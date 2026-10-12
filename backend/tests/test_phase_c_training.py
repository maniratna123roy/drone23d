"""Numerical Phase C regressions; these fixtures are never reconstruction outputs."""

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from pipeline import gaussian_optimizer as gs


@pytest.mark.parametrize("count", [251, 513])
def test_rasterizer_does_not_drop_candidates_after_250(count):
    colors = torch.zeros(count, 3)
    colors[:-1, 0] = 1.
    colors[-1, 1] = 1.
    opacity = torch.full((count,), 0.001)
    opacity[-1] = 0.8
    image = gs.rasterize_tiles(torch.zeros(count, 2), torch.arange(count), colors, opacity,
                               torch.eye(2).repeat(count, 1, 1), torch.full((count,), 3.), 2, 2)
    transmittance = 0.999 ** (count-1)
    assert image[0, 0, 0].item() == pytest.approx(1-transmittance, abs=1e-5)
    assert image[0, 0, 1].item() == pytest.approx(0.8*transmittance, abs=1e-5)


def test_offscreen_near_camera_splat_does_not_cover_image():
    projected = gs.project_gaussians(torch.tensor([[20., 10., 0.001]]), torch.full((1, 3), 0.01),
                                     torch.tensor([[1., 0., 0., 0.]]), torch.eye(3), torch.zeros(3),
                                     12., 12., 8., 6., 16, 12)
    assert projected is None


def test_tile_size_changes_memory_batching_not_the_image():
    means = torch.tensor([[4., 5.], [9., 8.], [14., 3.]])
    depths = torch.tensor([3., 2., 4.])
    colors = torch.tensor([[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    opacity = torch.tensor([0.4, 0.7, 0.3])
    inverse = torch.eye(2).repeat(3, 1, 1)*0.3
    radii = torch.full((3,), 6.)
    first = gs.rasterize_tiles(means, depths, colors, opacity, inverse, radii, 12, 16, tile_size=8)
    second = gs.rasterize_tiles(means, depths, colors, opacity, inverse, radii, 12, 16, tile_size=32)
    torch.testing.assert_close(first, second, atol=1e-6, rtol=1e-5)


def test_batched_renderer_matches_scalar_image_and_gradients():
    means = torch.tensor([[4., 5.], [9., 8.], [14., 3.]], requires_grad=True)
    colors = torch.tensor([[0.8, 0.1, 0.2], [0.1, 0.8, 0.3], [0.3, 0.1, 0.7]], requires_grad=True)
    opacity = torch.tensor([0.4, 0.7, 0.3], requires_grad=True)
    inverse = (torch.eye(2).repeat(3, 1, 1)*0.3).requires_grad_()
    parameters = (means, colors, opacity, inverse)
    reference = tuple(value.detach().clone().requires_grad_() for value in parameters)
    yy, xx = torch.meshgrid(torch.arange(12.), torch.arange(16.), indexing="ij")
    pixels = torch.stack((xx.flatten(), yy.flatten()), dim=1)
    expected = gs._composite_tile(*reference, pixels, torch.zeros(3)).reshape(12, 16, 3)
    actual = gs.rasterize_tiles(means, torch.tensor([1., 2., 3.]), colors, opacity, inverse,
                                torch.full((3,), 6.), 12, 16, tile_size=4)
    torch.testing.assert_close(actual, expected, atol=1e-6, rtol=1e-5)
    weights = torch.linspace(0.1, 1., actual.numel()).reshape_as(actual)
    (actual*weights).sum().backward()
    (expected*weights).sum().backward()
    for parameter, target in zip(parameters, reference):
        torch.testing.assert_close(parameter.grad, target.grad, atol=1e-5, rtol=1e-4)


def test_rasterizer_front_to_back_alpha_composition():
    # Deliberately reverse input depth order; near red contributes before far blue.
    image = gs.rasterize_tiles(torch.zeros(2, 2), torch.tensor([2., 1.]),
                               torch.tensor([[0., 0., 1.], [1., 0., 0.]]), torch.tensor([0.5, 0.5]),
                               torch.eye(2).repeat(2, 1, 1), torch.full((2,), 3.), 1, 1)
    torch.testing.assert_close(image[0, 0], torch.tensor([0.5, 0., 0.25]), atol=1e-6, rtol=0)


def test_renderer_gradients_reach_all_gaussian_parameters():
    xyz = torch.tensor([[0.1, 0.2, 3.], [-0.2, 0., 4.]], requires_grad=True)
    scales = torch.tensor([[0.12, 0.25, 0.08], [0.22, 0.09, 0.11]], requires_grad=True)
    rotations = torch.tensor([[1., 0.2, 0.1, 0.05], [1., 0.1, 0.2, 0.1]], requires_grad=True)
    opacity = torch.tensor([0.6, 0.8], requires_grad=True)
    colors = torch.tensor([[0.8, 0.2, 0.1], [0.1, 0.3, 0.7]], requires_grad=True)
    projected = gs.project_gaussians(xyz, scales, rotations, torch.eye(3), torch.zeros(3), 12, 12, 8, 6, 16, 12)
    idx = projected["indices"]
    image = gs.rasterize_tiles(torch.stack((projected["u"], projected["v"]), dim=1), projected["z"],
                               colors[idx], opacity[idx], projected["inv_cov2d"], projected["radius"], 12, 16)
    weights = torch.linspace(0.1, 1., image.numel()).reshape_as(image)
    (image * weights).sum().backward()
    for parameter in (xyz, scales, rotations, opacity, colors):
        assert parameter.grad is not None
        assert torch.isfinite(parameter.grad).all()
        assert parameter.grad.abs().sum().item() > 0


def test_zero_depth_culled_points_do_not_poison_gradients():
    xyz = torch.tensor([[0.1, 0.2, 3.], [0., 0., 0.]], requires_grad=True)
    projected = gs.project_gaussians(xyz, torch.full((2, 3), 0.1), torch.tensor([[1., 0., 0., 0.]] * 2),
                                     torch.eye(3), torch.zeros(3), 10., 10., 4., 4., 8, 8)
    (projected["u"].sum() + projected["v"].sum()).backward()
    assert torch.isfinite(xyz.grad).all()


@pytest.mark.parametrize("count", [1, 2, 3])
def test_small_gaussian_initialization_is_valid(count):
    positions = np.column_stack((np.arange(count) * 0.1, np.zeros(count), np.ones(count))).astype(np.float32)
    model = gs.GaussianModel(positions, np.full((count, 3), 128, np.uint8), torch.device("cpu"))
    assert torch.isfinite(model.get_scaling()).all()
    assert (model.get_scaling() > 0).all()


def test_pruning_small_models_really_removes_transparent_points():
    model = gs.GaussianModel(np.array([[0., 0., 2.], [0.1, 0., 2.]], np.float32),
                             np.full((2, 3), 128, np.uint8), torch.device("cpu"))
    with torch.no_grad():
        model._opacity[0] = -20.
    model.prune_gaussians()
    assert len(model.get_xyz()) == 1


def test_pruning_never_silently_keeps_an_all_transparent_model():
    model = gs.GaussianModel(np.array([[0., 0., 2.]], np.float32), np.full((1, 3), 128, np.uint8), torch.device("cpu"))
    with torch.no_grad():
        model._opacity[:] = -20.
    with pytest.raises(ValueError, match="all"):
        model.prune_gaussians()


def test_legacy_serialization_cli_cannot_claim_phase_c(monkeypatch, capsys):
    from pipeline import colmap_reconstructor
    monkeypatch.setattr(colmap_reconstructor, "stage_c_export_3dgs", lambda **kw: pytest.fail("no raw point export"))
    assert colmap_reconstructor.main(["--stage", "stage_c"]) == 1
    assert "pipeline.gaussian_optimizer" in capsys.readouterr().err


def test_view_split_is_disjoint_and_has_both_groups():
    training, validation = gs.split_view_names([f"frame_{i:02d}.jpg" for i in range(11)])
    assert set(training).isdisjoint(validation)
    assert len(training) == 9 and len(validation) == 2
    assert len(training) + len(validation) == 11


def test_failed_phase_b_never_starts_training(tmp_path):
    (tmp_path / "dense_quality_report.json").write_text(json.dumps({"status": "FAILED"}))
    with pytest.raises(ValueError, match="Phase B"):
        gs.load_phase_b_inputs(tmp_path)


def test_empty_surface_mask_is_rejected():
    image = torch.zeros(8, 8, 3)
    with pytest.raises(ValueError, match="support"):
        gs.photometric_loss(image, image, torch.zeros(8, 8, dtype=torch.bool), gs.create_ssim_window(11, 3, "cpu"))


def test_quality_gate_cannot_pass_without_improvement():
    baseline = {"surface_psnr_db": 22., "surface_ssim": 0.7, "surface_l1": 0.08}
    final = {"surface_psnr_db": 21., "surface_ssim": 0.65, "surface_l1": 0.09}
    report = gs.evaluate_quality_gate(baseline, final, steps=100, finite_parameters=True)
    assert report["status"] == "FAILED"
    assert "heldout_improvement" in report["failed_checks"]


def test_quality_gate_rejects_nonfinite_metrics():
    baseline = {"surface_psnr_db": 15., "surface_ssim": 0.4, "surface_l1": 0.2}
    final = {"surface_psnr_db": float("nan"), "surface_ssim": 0.9, "surface_l1": 0.01}
    assert gs.evaluate_quality_gate(baseline, final, steps=100, finite_parameters=True)["status"] == "FAILED"


def test_quality_gate_passes_only_measured_improved_quality():
    baseline = {"surface_psnr_db": 15., "surface_ssim": 0.4, "surface_l1": 0.2}
    final = {"surface_psnr_db": 23., "surface_ssim": 0.8, "surface_l1": 0.04}
    report = gs.evaluate_quality_gate(baseline, final, steps=100, finite_parameters=True)
    assert report["status"] == "PASSED"
    assert gs.evaluate_quality_gate(baseline, final, steps=0, finite_parameters=True)["status"] == "FAILED"
    assert gs.evaluate_quality_gate(baseline, final, steps=100, finite_parameters=False)["status"] == "FAILED"


def test_optimized_export_preserves_frame_opacity_and_unknown_semantics(tmp_path):
    from pipeline.common.io import load_ply
    xyz = np.array([[0.1, 0.2, 2.], [0.4, -0.2, 3.]], np.float32)
    rgb = np.array([[120, 30, 210], [40, 160, 80]], np.uint8)
    model = gs.GaussianModel(xyz, rgb, torch.device("cpu"))
    with torch.no_grad():
        model._opacity[:] = torch.tensor([[-0.8], [1.3]])
    metadata = gs.export_optimized_web_splat(model, tmp_path)
    assert metadata["scene_published"] is False
    assert metadata["ground_alignment_applied"] is False
    assert metadata["coordinate_frame"] == "COLMAP_PHASE_A"
    assert (tmp_path / "scene.classes.u8").read_bytes() == bytes([255, 255])
    assert (tmp_path / "scene.splat").stat().st_size == 64
    decoded = gs.decode_splat(tmp_path / "scene.splat", torch.device("cpu"))
    torch.testing.assert_close(decoded.get_xyz(), model.get_xyz())
    torch.testing.assert_close(decoded.get_scaling(), model.get_scaling())
    torch.testing.assert_close(decoded.get_opacity(), model.get_opacity(), atol=1/255, rtol=0)
    restored = load_ply(str(tmp_path / "optimized_gaussians.ply"))
    np.testing.assert_allclose(restored["positions"], xyz)
    np.testing.assert_allclose(restored["opacities"], model.get_opacity().detach().numpy(), atol=1e-6)


def test_tensor_only_checkpoint_restores_every_parameter(tmp_path):
    model = gs.GaussianModel(np.array([[0., 0., 2.], [0.1, 0., 2.]], np.float32),
                             np.array([[40, 80, 120], [150, 30, 10]], np.uint8), torch.device("cpu"))
    with torch.no_grad():
        model._opacity[:] = 0.12
        model._rotation[0] = torch.tensor([1., 0.1, 0.2, 0.3])
    path = tmp_path / "model.pt"
    torch.save({"model": model.state_dict(), "phase_b_point_indices": torch.tensor([4, 9])}, path)
    restored = gs.load_gaussian_checkpoint(path, torch.device("cpu"))
    for name, value in model.state_dict().items():
        assert torch.equal(value, restored.state_dict()[name])


def test_centers_remain_near_measured_surface_anchors():
    model = gs.GaussianModel(np.array([[0., 0., 2.], [0.1, 0., 2.]], np.float32),
                             np.full((2, 3), 128, np.uint8), torch.device("cpu"))
    with torch.no_grad():
        model._xyz.add_(100)
        model._scaling.add_(100)
    model.constrain_to_observations()
    displacement = (model.get_xyz()-model.anchor_xyz).norm(dim=1)
    assert torch.all(displacement <= model.anchor_scales[:, 0]*2+1e-6)
    assert torch.all(model.get_scaling() <= model.anchor_scales*4+1e-6)
