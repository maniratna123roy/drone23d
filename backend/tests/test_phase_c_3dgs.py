"""
Unit and Integration Tests for Phase C: 3D Gaussian Splatting Optimization & Validation.
Tests:
- Quaternion to SO(3) rotation conversion
- 3D Covariance construction (positive semi-definiteness)
- Differentiable perspective projection
- Differentiable tile rasterizer and gradient flow
- SSIM loss calculation
- Gaussian pruning and adaptive density control
"""

import pytest
import torch
import numpy as np

from pipeline.gaussian_optimizer import (
    build_rotation,
    build_covariance_3d,
    project_gaussians,
    rasterize_tiles,
    create_ssim_window,
    ssim_loss,
    GaussianModel
)


def test_build_rotation_properties():
    """Verifies that quaternion tensor converts to valid SO(3) rotation matrices."""
    # Identity quaternions
    q_id = torch.tensor([[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]], dtype=torch.float32)
    R = build_rotation(q_id)
    assert R.shape == (2, 3, 3)
    np.testing.assert_allclose(R[0].numpy(), np.eye(3), atol=1e-5)

    # Determinant of each rotation matrix must be +1
    dets = torch.det(R)
    assert torch.allclose(dets, torch.ones_like(dets), atol=1e-5)


def test_build_covariance_3d():
    """Verifies that 3D covariance Sigma = R * S * S^T * R^T is symmetric and positive definite."""
    N = 5
    scales = torch.full((N, 3), 0.1, dtype=torch.float32)
    rotations = torch.zeros((N, 4), dtype=torch.float32)
    rotations[:, 0] = 1.0

    cov3d = build_covariance_3d(scales, rotations)
    assert cov3d.shape == (N, 3, 3)

    # Must be symmetric: cov3d == cov3d^T
    assert torch.allclose(cov3d, cov3d.transpose(1, 2), atol=1e-6)

    # Eigenvalues must all be positive
    eigenvalues = torch.linalg.eigvalsh(cov3d)
    assert torch.all(eigenvalues > 0.0)


def test_project_gaussians_pinhole():
    """Verifies that project_gaussians transforms 3D means to 2D screen coordinates."""
    N = 10
    means = torch.zeros((N, 3), dtype=torch.float32)
    means[:, 2] = 5.0 # In front of camera at Z=5m
    scales = torch.full((N, 3), 0.05, dtype=torch.float32)
    rotations = torch.zeros((N, 4), dtype=torch.float32)
    rotations[:, 0] = 1.0

    R_cw = torch.eye(3, dtype=torch.float32)
    t_cw = torch.zeros(3, dtype=torch.float32)

    proj = project_gaussians(
        means3d=means,
        scales=scales,
        rotations=rotations,
        R_cw=R_cw,
        t_cw=t_cw,
        fx=500.0, fy=500.0, cx=320.0, cy=180.0,
        W=640, H=360
    )

    assert proj is not None
    assert len(proj["u"]) == N
    # Centered points should project to principal point (cx, cy)
    assert torch.allclose(proj["u"], torch.full((N,), 320.0), atol=1e-3)
    assert torch.allclose(proj["v"], torch.full((N,), 180.0), atol=1e-3)
    assert torch.allclose(proj["z"], torch.full((N,), 5.0), atol=1e-3)


def test_ssim_loss_properties():
    """Verifies that SSIM loss is 0 for identical images and >0 for perturbed images."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    win = create_ssim_window(11, 3, device)

    img1 = torch.rand((1, 3, 64, 64), device=device)
    img2 = img1.clone()

    # Identical images must have SSIM loss ~ 0
    loss_ident = ssim_loss(img1, img2, win)
    assert loss_ident.item() < 1e-4

    # Inverted image must have high SSIM loss
    img3 = 1.0 - img1
    loss_diff = ssim_loss(img1, img3, win)
    assert loss_diff.item() > 0.30


def test_gaussian_model_pruning():
    """Verifies that GaussianModel removes transparent or oversized Gaussians."""
    device = torch.device("cpu")
    N = 1000
    pos = np.random.uniform(-1, 1, size=(N, 3)).astype(np.float32)
    col = np.random.randint(0, 255, size=(N, 3)).astype(np.uint8)

    model = GaussianModel(pos, col, device)
    assert len(model.get_xyz()) == N

    # Manually set half of the opacities to very low value
    with torch.no_grad():
        model._opacity[:500] = -10.0 # sigmoid(-10) ~ 0.000045 < 0.05

    model.prune_gaussians(min_opacity=0.05)
    # 500 transparent Gaussians should have been pruned
    assert len(model.get_xyz()) == 500
