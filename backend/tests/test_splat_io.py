"""Numeric serialization fixtures only; no scene generation, training, or services."""

import struct

import numpy as np
import pytest
from plyfile import PlyData, PlyElement

from pipeline.common.io import load_ply, save_classes, save_ply, save_splat


def write_vertex(path, columns, *, text=False):
    data = np.empty(len(next(iter(columns.values()))), dtype=[
        (name, np.asarray(values).dtype) for name, values in columns.items()
    ])
    for name, values in columns.items():
        data[name] = values
    PlyData([PlyElement.describe(data, "vertex")], text=text).write(str(path))


def xyz_columns():
    return dict(zip(("x", "y", "z"), np.array([
        [3., -1., 8.], [-7., 4., 2.], [0., 9., -6.],
    ], dtype=np.float32).T))


@pytest.mark.parametrize("text", [False, True], ids=["binary", "ascii"])
@pytest.mark.parametrize("with_normals", [False, True])
def test_load_measured_rgb_and_optional_normals(tmp_path, text, with_normals):
    columns = xyz_columns()
    rgb = np.array([[162, 194, 216], [0, 255, 19], [71, 8, 143]], dtype=np.uint8)
    columns.update(zip(("red", "green", "blue"), rgb.T))
    normals = np.array([[0., 0., -1.], [.3, -.4, .5], [1., 0., 0.]], dtype=np.float32)
    if with_normals:
        columns.update(zip(("nx", "ny", "nz"), normals.T))
    path = tmp_path / "measured.ply"
    write_vertex(path, columns, text=text)

    result = load_ply(str(path))

    np.testing.assert_array_equal(result["positions"], np.column_stack(list(xyz_columns().values())))
    np.testing.assert_array_equal(result["colors"][:, :3], rgb)
    np.testing.assert_array_equal(result["colors"][:, 3], [255, 255, 255])
    np.testing.assert_array_equal(result["opacities"], [1., 1., 1.])
    np.testing.assert_array_equal(result["rotations"], [[1., 0., 0., 0.]] * 3)
    np.testing.assert_allclose(result["scales"], .05)
    assert result["colors"].dtype == np.uint8
    if with_normals:
        np.testing.assert_array_equal(result["normals"], normals)
        assert result["normals"].dtype == np.float32
    else:
        assert "normals" not in result  # Never invent measured normals.


def test_load_rgba_without_logits_preserves_alpha(tmp_path):
    columns = xyz_columns()
    rgba = np.array([[1, 2, 3, 0], [4, 5, 6, 17], [7, 8, 9, 255]], dtype=np.uint8)
    columns.update(zip(("red", "green", "blue", "alpha"), rgba.T))
    path = tmp_path / "rgba.ply"
    write_vertex(path, columns)
    result = load_ply(str(path))
    np.testing.assert_array_equal(result["colors"], rgba)
    np.testing.assert_allclose(result["opacities"], rgba[:, 3] / 255.)


def test_load_gaussian_sh_log_scales_wxyz_and_extreme_logits(tmp_path):
    columns = xyz_columns()
    dc = np.array([[-3., 0., 3.], [0., 1., -1.], [.5, -.5, 0.]], dtype=np.float32)
    scales = np.array([[1e-6, .2, 2.], [.03, .04, .05], [1., 3., 7.]], dtype=np.float32)
    rotations = np.array([[2., 0., 0., 0.], [1., -2., 3., -4.], [-2., 0., 0., 0.]], dtype=np.float32)
    columns.update(zip(("f_dc_0", "f_dc_1", "f_dc_2"), dc.T))
    columns.update(zip(("scale_0", "scale_1", "scale_2"), np.log(scales).T))
    columns.update(zip(("rot_0", "rot_1", "rot_2", "rot_3"), rotations.T))
    columns["opacity"] = np.array([-1000., 0., 1000.], dtype=np.float32)
    path = tmp_path / "gaussian.ply"
    write_vertex(path, columns)

    with np.errstate(over="raise", invalid="raise"):
        result = load_ply(str(path))

    expected_rgb = np.clip((.5 + .28209479177387814 * dc) * 255, 0, 255).astype(np.uint8)
    np.testing.assert_array_equal(result["colors"][:, :3], expected_rgb)
    np.testing.assert_allclose(result["scales"], scales, rtol=1e-6)
    np.testing.assert_allclose(result["rotations"], rotations / np.linalg.norm(rotations.astype(np.float64), axis=1, keepdims=True))
    np.testing.assert_array_equal(result["opacities"], [0., .5, 1.])
    np.testing.assert_array_equal(result["colors"][:, 3], [0, 128, 255])
    assert all(result[key].dtype == np.float32 for key in ("positions", "scales", "rotations", "opacities"))

    # This is the real exporter contract: alpha travels in colors, not a separate argument.
    binary = tmp_path / "gaussian.splat"
    save_splat(result["positions"], result["scales"], result["rotations"], result["colors"], str(binary))
    rows = list(struct.iter_unpack("<6f8B", binary.read_bytes()))
    assert [row[9] for row in rows] == [0, 128, 255]


def test_learned_opacity_overrides_legacy_alpha_without_replacing_rgb(tmp_path):
    columns = xyz_columns()
    rgba = np.array([[10, 20, 30, 255], [40, 50, 60, 255], [70, 80, 90, 255]], dtype=np.uint8)
    columns.update(zip(("red", "green", "blue", "alpha"), rgba.T))
    columns["opacity"] = np.array([-np.log(3.), 0., np.log(3.)], dtype=np.float32)
    path = tmp_path / "learned.ply"
    write_vertex(path, columns)
    result = load_ply(str(path))
    np.testing.assert_array_equal(result["colors"][:, :3], rgba[:, :3])
    np.testing.assert_allclose(result["opacities"], [.25, .5, .75])
    np.testing.assert_array_equal(result["colors"][:, 3], [64, 128, 191])


def test_uncolored_ply_defaults_to_opaque_gray(tmp_path):
    path = tmp_path / "positions.ply"
    write_vertex(path, xyz_columns())
    result = load_ply(str(path))
    np.testing.assert_array_equal(result["colors"], [[200, 200, 200, 255]] * 3)
    np.testing.assert_array_equal(result["opacities"], [1., 1., 1.])


@pytest.mark.parametrize("field", ["red", "f_dc_0", "scale_0", "rot_0", "nx"])
def test_load_rejects_partial_property_groups(tmp_path, field):
    columns = xyz_columns()
    columns[field] = np.ones(3, dtype=np.float32)
    path = tmp_path / "incomplete.ply"
    write_vertex(path, columns)
    with pytest.raises(ValueError, match="[Ii]ncomplete|missing"):
        load_ply(str(path))


def test_save_ply_roundtrip_preserves_small_scales_and_opacity_boundaries(tmp_path):
    positions = np.array([[3., 2., 1.], [-4., 5., 6.], [7., -8., 9.], [0., 1., 2.]], dtype=np.float32)
    colors = np.array([[2, 17, 255], [32, 64, 128], [201, 18, 0], [3, 4, 5]], dtype=np.uint8)
    scales = np.array([[1e-6, 1e-5, 1e-4], [.2, .3, .4], [1., 2., 3.], [.01, .02, .03]], dtype=np.float32)
    rotations = np.array([[2., 0., 0., 0.], [0., 3., 0., 0.], [1., -2., 3., -4.], [-1., 0., 0., 0.]], dtype=np.float32)
    opacity = np.array([0., 1e-5, .99999, 1.], dtype=np.float32)
    path = tmp_path / "roundtrip.ply"

    with np.errstate(over="raise", invalid="raise", divide="raise"):
        save_ply(str(path), positions, colors, scales, rotations, opacity)
        result = load_ply(str(path))

    np.testing.assert_array_equal(result["positions"], positions)
    np.testing.assert_array_equal(result["colors"][:, :3], colors)
    np.testing.assert_allclose(result["scales"], scales, rtol=1e-6)
    np.testing.assert_allclose(result["rotations"], rotations / np.linalg.norm(rotations.astype(np.float64), axis=1, keepdims=True))
    np.testing.assert_allclose(result["opacities"], opacity, rtol=1e-6)
    np.testing.assert_array_equal(result["colors"][:, 3], [0, 0, 255, 255])


def test_save_ply_uses_rgba_alpha_when_no_separate_opacity_is_supplied(tmp_path):
    rgba = np.array([[1, 2, 3, 0], [4, 5, 6, 17], [7, 8, 9, 255]], dtype=np.uint8)
    path = tmp_path / "rgba.ply"
    save_ply(str(path), np.column_stack(list(xyz_columns().values())), rgba)
    result = load_ply(str(path))
    np.testing.assert_array_equal(result["colors"], rgba)
    np.testing.assert_allclose(result["opacities"], rgba[:, 3] / 255.)


@pytest.mark.parametrize("fields,match", [
    ({"x": np.nan}, "positions"),
    ({"red": 256., "green": 0., "blue": 0.}, "colors"),
    ({"red": np.nan, "green": 0., "blue": 0.}, "colors"),
    ({"f_dc_0": np.nan, "f_dc_1": 0., "f_dc_2": 0.}, "colors"),
    ({"nx": np.inf, "ny": 0., "nz": 1.}, "normals"),
    ({"scale_0": 1000., "scale_1": 0., "scale_2": 0.}, "scales"),
    ({"scale_0": -1000., "scale_1": 0., "scale_2": 0.}, "scales"),
    ({"rot_0": 0., "rot_1": 0., "rot_2": 0., "rot_3": 0.}, "rotations"),
    ({"opacity": np.nan}, "opacity"),
])
def test_load_rejects_invalid_numeric_properties(tmp_path, fields, match):
    columns = xyz_columns()
    columns.update({name: np.full(3, value, dtype=np.float32) for name, value in fields.items()})
    path = tmp_path / "invalid.ply"
    write_vertex(path, columns)
    with np.errstate(over="raise", invalid="raise", divide="raise", under="raise"):
        with pytest.raises(ValueError, match=match):
            load_ply(str(path))


@pytest.mark.parametrize("opacity", [np.nan, np.inf, -.01, 1.01])
def test_save_ply_rejects_invalid_opacity_without_writing(tmp_path, opacity):
    path = tmp_path / "invalid.ply"
    with pytest.raises(ValueError, match="opacities"):
        save_ply(str(path), np.zeros((1, 3)), np.zeros((1, 3)), opacities=np.array([opacity]))
    assert not path.exists()


def splat_arrays():
    return {
        "positions": np.array([[3., 2., 1.], [-4., 5., 6.], [7., -8., 9.]], dtype=np.float64),
        "scales": np.array([[.01, .02, .03], [3., 2., 1.], [.2, .3, .4]], dtype=np.float64),
        "rotations": np.array([[2., 0., 0., 0.], [0., -3., 0., 0.], [1., -2., 3., -4.]], dtype=np.float64),
        "colors": np.array([[12, 23, 34, 0], [45, 56, 67, 17], [78, 89, 90, 255]], dtype=np.uint8),
    }


def test_splat_binary_layout_rgba_wxyz_and_class_order(tmp_path):
    arrays = splat_arrays()
    originals = {name: value.copy() for name, value in arrays.items()}
    path = tmp_path / "nested" / "roundtrip.splat"
    save_splat(**arrays, out_path=str(path))
    rows = np.array(list(struct.iter_unpack("<6f8B", path.read_bytes())))
    assert path.stat().st_size == 32 * 3
    np.testing.assert_array_equal(rows[:, :3], arrays["positions"].astype(np.float32))
    np.testing.assert_array_equal(rows[:, 3:6], arrays["scales"].astype(np.float32))
    np.testing.assert_array_equal(rows[:, 6:10], arrays["colors"])
    # WXYZ, not XYZW; +1 clips to 255 and -1 encodes as 0.
    np.testing.assert_array_equal(rows[:2, 10:], [[255, 128, 128, 128], [128, 0, 128, 128]])
    decoded_q = (rows[:, 10:] - 128.) / 128.
    expected_q = arrays["rotations"] / np.linalg.norm(arrays["rotations"], axis=1, keepdims=True)
    np.testing.assert_allclose(decoded_q, expected_q, atol=1 / 128, rtol=0)
    for name in arrays:
        np.testing.assert_array_equal(arrays[name], originals[name])
    classes_path = tmp_path / "roundtrip.classes.u8"
    save_classes(np.array([3, 255, 0], dtype=np.uint8), str(classes_path))
    assert classes_path.read_bytes() == bytes([3, 255, 0])


@pytest.mark.parametrize("magnitude", [1e-300, 1e300])
def test_splat_normalization_is_stable_for_finite_extreme_quaternions(tmp_path, magnitude):
    arrays = splat_arrays()
    arrays["rotations"] = np.tile([magnitude, -magnitude, magnitude, -magnitude], (3, 1))
    path = tmp_path / "extreme.splat"
    with np.errstate(over="raise", invalid="raise", divide="raise", under="raise"):
        save_splat(**arrays, out_path=str(path))
    rows = list(struct.iter_unpack("<6f8B", path.read_bytes()))
    assert [row[10:] for row in rows] == [(192, 64, 192, 64)] * 3


@pytest.mark.parametrize("name,width", [("positions", 3), ("scales", 3), ("rotations", 4), ("colors", 4)])
@pytest.mark.parametrize("shape_case", ["short", "broadcast", "columns", "flat"])
def test_splat_rejects_mismatched_shapes_without_creating_output(tmp_path, name, width, shape_case):
    arrays = splat_arrays()
    shapes = {"short": (2, width), "broadcast": (1, width), "columns": (3, width - 1), "flat": (3 * width,)}
    arrays[name] = np.ones(shapes[shape_case])
    path = tmp_path / "not_created" / "invalid.splat"
    with pytest.raises(ValueError, match=name):
        save_splat(**arrays, out_path=str(path))
    assert not path.parent.exists()


@pytest.mark.parametrize("name", ["positions", "scales", "rotations", "colors"])
@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_splat_rejects_nonfinite_values_without_overwriting_output(tmp_path, name, value):
    arrays = splat_arrays()
    arrays[name] = arrays[name].astype(np.float64)
    arrays[name][0, 0] = value
    path = tmp_path / "existing.splat"
    path.write_bytes(b"keep existing bytes")
    with pytest.raises(ValueError, match=name):
        save_splat(**arrays, out_path=str(path))
    assert path.read_bytes() == b"keep existing bytes"


@pytest.mark.parametrize("name,value", [
    ("scales", 0.), ("scales", -1.), ("scales", 1e-100),
    ("scales", 1e100), ("positions", 1e100),
    ("colors", -1.), ("colors", 256.), ("colors", 12.5),
])
def test_splat_rejects_unrepresentable_values(tmp_path, name, value):
    arrays = splat_arrays()
    arrays[name] = arrays[name].astype(np.float64)
    arrays[name][0, 0] = value
    with np.errstate(over="raise", invalid="raise", under="raise"):
        with pytest.raises(ValueError, match=name):
            save_splat(**arrays, out_path=str(tmp_path / "invalid.splat"))


def test_splat_rejects_zero_quaternion(tmp_path):
    arrays = splat_arrays()
    arrays["rotations"][1] = 0.
    with pytest.raises(ValueError, match="rotations"):
        save_splat(**arrays, out_path=str(tmp_path / "invalid.splat"))


@pytest.mark.parametrize("name", ["positions", "scales", "rotations", "colors"])
@pytest.mark.parametrize("dtype", ["complex128", "str"])
def test_splat_rejects_non_real_numeric_arrays(tmp_path, name, dtype):
    arrays = splat_arrays()
    arrays[name] = arrays[name].astype(dtype)
    with pytest.raises(ValueError, match=name):
        save_splat(**arrays, out_path=str(tmp_path / "invalid.splat"))


def test_splat_float32_boundaries_and_empty_input(tmp_path):
    arrays = splat_arrays()
    arrays["positions"][0, 0] = np.finfo(np.float32).max
    arrays["scales"][0, 0] = np.finfo(np.float32).smallest_subnormal
    path = tmp_path / "boundaries.splat"
    save_splat(**arrays, out_path=str(path))
    rows = list(struct.iter_unpack("<6f8B", path.read_bytes()))
    assert rows[0][0] == np.finfo(np.float32).max
    assert rows[0][3] == np.finfo(np.float32).smallest_subnormal
    empty = {name: value[:0] for name, value in arrays.items()}
    save_splat(**empty, out_path=str(path))
    assert path.read_bytes() == b""
