import test from "node:test";
import assert from "node:assert/strict";
import { Matrix4, PerspectiveCamera } from "three";
import {
  parseGaussianSplat,
  projectGaussian,
  sortGaussiansBackToFront,
  gaussianAlpha,
} from "../src/components/three/gaussian-data.ts";
import { binary, classes } from "./verified-fixtures.mjs";

const identity = new Matrix4().elements;
const camera = new PerspectiveCamera(60, 1, 0.1, 100);
function parse(rows = [{}]) {
  return parseGaussianSplat(binary(rows), classes(rows.length), rows.length);
}
function project(data, modelView = identity, width = 800, height = 800) {
  const result = new Float64Array(7);
  const visible = projectGaussian(
    data,
    0,
    modelView,
    camera.projectionMatrix.elements,
    width,
    height,
    0.1,
    100,
    result,
  );
  return { visible, result };
}
function close(a, b, tolerance = 1e-6) {
  assert.ok(Math.abs(a - b) <= tolerance, `${a} differs from ${b}`);
}

test("decodes real 32-byte little-endian XYZ/scale/RGBA/WXYZ records without rearranging rows", () => {
  const data = parse([
    { position: [1.25, -2.5, -10], scale: [0.25, 2, 3], color: [17, 83, 241, 64] },
    { position: [-4, 7, -20], color: [0, 255, 1, 0] },
  ]);
  assert.equal(data.count, 2);
  assert.deepEqual([...data.positions], [1.25, -2.5, -10, -4, 7, -20]);
  assert.deepEqual([...data.scales.slice(0, 3)], [0.25, 2, 3]);
  close(data.colors[3], 64 / 255);
  assert.equal(data.colors[7], 0);
  assert.deepEqual([...data.rotations.slice(0, 4)], [1, 0, 0, 0]);
  assert.deepEqual([...data.classes], [255, 255]);
  assert.deepEqual([...data.covariance.slice(0, 6)], [0.0625, 0, 0, 4, 0, 9]);
});

test("normalizes quantized WXYZ, including a non-unit negative quaternion", () => {
  const data = parse([{ quaternion: [-0.5, -0.5, 0, 0] }]);
  close(Math.hypot(...data.rotations), 1);
  close(data.rotations[0], -Math.SQRT1_2);
  close(data.rotations[1], -Math.SQRT1_2);
  // Rotation around X exchanges Y/Z variance, not X/Y as an XYZW misread would.
  close(data.covariance[0], 4);
  close(data.covariance[3], 0.25);
  close(data.covariance[5], 1);
});

test("rejects short, trailing, empty, count-mismatched and malformed assets", () => {
  for (const size of [0, 1, 31, 33, 63, 64])
    assert.throws(() => parseGaussianSplat(new ArrayBuffer(size), classes(), 1), /length/);
  for (const count of [0, -1, 1.5, NaN])
    assert.throws(() => parseGaussianSplat(binary(), classes(), count), /count/);
  assert.throws(() => parseGaussianSplat(binary(), new ArrayBuffer(0), 1), /sidecar/);
  assert.throws(() => parseGaussianSplat(binary(), new Uint8Array([0]).buffer, 1), /UNKNOWN/);
  for (const position of [
    [NaN, 0, 0],
    [0, Infinity, 0],
  ])
    assert.throws(() => parse([{ position }]), /finite/);
  for (const scale of [
    [0, 1, 1],
    [1, -1, 1],
    [1, 1, Infinity],
  ])
    assert.throws(() => parse([{ scale }]), /positive/);
  assert.throws(() => parse([{ quaternion: [0, 0, 0, 0] }]), /zero-length/);
});

test("projects anisotropic scale, including perspective distance and camera focal length", () => {
  const near = project(parse());
  assert.equal(near.visible, true);
  close(near.result[0], 0);
  close(near.result[1], 0);
  const major = Math.hypot(near.result[3], near.result[4]);
  const minor = Math.hypot(near.result[5], near.result[6]);
  close(major / minor, 2, 0.0001);
  const farther = project(parse([{ position: [0, 0, -20] }])).result;
  close(Math.hypot(farther[3], farther[4]) / major, 0.5, 0.0001);
  const expectedMajor =
    (3 * Math.sqrt(((camera.projectionMatrix.elements[0] * 400) / 10) ** 2 * 4 + 0.3) * 2) / 800;
  close(major, expectedMajor);
});

test("WXYZ rotation changes projected ellipse orientation instead of drawing circular sprites", () => {
  const horizontal = project(parse()).result;
  const vertical = project(parse([{ quaternion: [Math.SQRT1_2, 0, 0, Math.SQRT1_2] }])).result;
  assert.ok(Math.abs(horizontal[3]) > 100 * Math.abs(horizontal[4]));
  assert.ok(Math.abs(vertical[4]) > 100 * Math.abs(vertical[3]));
  close(Math.hypot(horizontal[3], horizontal[4]), Math.hypot(vertical[3], vertical[4]));
});

test("projection uses the full covariance under source/camera rotation and non-square viewports", () => {
  const data = parse([{ quaternion: [Math.cos(Math.PI / 8), 0, 0, Math.sin(Math.PI / 8)] }]);
  const before = [...data.positions];
  const projected = project(data).result;
  assert.ok(Math.abs(projected[3]) > 0.1 && Math.abs(projected[4]) > 0.1);
  const rotated = project(data, new Matrix4().makeRotationZ(-Math.PI / 4).elements).result;
  assert.ok(Math.abs(rotated[3]) > 50 * Math.abs(rotated[4]));
  const wide = project(data, identity, 1600, 800).result;
  assert.ok([...wide].every(Number.isFinite));
  assert.deepEqual(
    [...data.positions],
    before,
    "projection must not align/scale/mutate source positions",
  );
});

test("rejects near/far/behind-camera, transparent and offscreen Gaussians", () => {
  for (const z of [1, 0, -0.01, -101])
    assert.equal(project(parse([{ position: [0, 0, z] }])).visible, false);
  assert.equal(project(parse([{ color: [255, 255, 255, 0] }])).visible, false);
  assert.equal(
    project(parse([{ position: [1e5, 0, -10], scale: [0.01, 0.01, 0.00001] }])).visible,
    false,
  );
});

test("off-axis near-camera Gaussians cannot balloon across the viewport", () => {
  const data = parse([{ position: [20, 10, -0.001], scale: [0.01, 0.01, 0.01] }]);
  const result = new Float64Array(7);
  assert.equal(
    projectGaussian(data, 0, identity, camera.projectionMatrix.elements, 640, 360, 0.00001, 100, result),
    false,
  );
  assert.ok(result[0] > 1000, "the projected center itself must not be clamped into view");
});

test("sorts by camera-space depth far-to-near, with stable ties and camera rotation", () => {
  const positions = new Float32Array([1, 0, -3, 2, 0, -12, 3, 0, -7, 4, 0, -7]);
  assert.deepEqual([...sortGaussiansBackToFront(positions, identity)], [1, 2, 3, 0]);
  // Exact half-turn (sin(pi) floating-point residue must not turn a tie into a different test case).
  assert.deepEqual(
    [...sortGaussiansBackToFront(positions, new Matrix4().makeScale(-1, 1, -1).elements)],
    [0, 2, 3, 1],
  );
  assert.deepEqual(
    [...sortGaussiansBackToFront(positions, new Matrix4().makeRotationY(Math.PI / 2).elements)],
    [3, 2, 1, 0],
  );
});

test("learned alpha follows the Gaussian falloff and blends in depth order", () => {
  const opacity = parse()["colors"][3];
  close(gaussianAlpha(opacity, 0, 0), 128 / 255);
  close(gaussianAlpha(opacity, 1, 0), opacity * Math.exp(-0.5));
  assert.equal(gaussianAlpha(0, 0, 0), 0);
  assert.equal(gaussianAlpha(1, 0, 0), 0.99);
  assert.equal(gaussianAlpha(opacity, 3.1, 0), 0);
  const data = parse([
    { position: [0, 0, -3], color: [255, 0, 0, 128] },
    { position: [0, 0, -12], color: [0, 0, 255, 128] },
  ]);
  let rgb = [0, 0, 0];
  for (const i of sortGaussiansBackToFront(data.positions, identity)) {
    const alpha = gaussianAlpha(data.colors[i * 4 + 3], 0, 0);
    rgb = rgb.map((channel, j) => data.colors[i * 4 + j] * alpha + channel * (1 - alpha));
  }
  close(rgb[0], opacity);
  close(rgb[2], opacity * (1 - opacity));
  assert.ok(rgb[0] > rgb[2], "the nearer red Gaussian must cover the farther blue one");
});
