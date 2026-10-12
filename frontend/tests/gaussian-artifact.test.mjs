import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { Matrix4, Quaternion, PerspectiveCamera } from "three";
import {
  parseGaussianSplat,
  projectGaussian,
  sortGaussiansBackToFront,
} from "../src/components/three/gaussian-data.ts";

const root = new URL("../../", import.meta.url);
const splatPath = new URL("output/phase_c/real_drone_train_01/assets/scene.splat", root);
const sidecarPath = new URL("output/phase_c/real_drone_train_01/assets/scene.classes.u8", root);
const posesPath = new URL(
  "output/phase_b/real_drone_20261002/undistorted_sparse_txt/images.txt",
  root,
);
const camerasPath = new URL(
  "output/phase_b/real_drone_20261002/undistorted_sparse_txt/cameras.txt",
  root,
);
const available = [splatPath, sidecarPath, posesPath, camerasPath].every(existsSync);
function arrayBuffer(path) {
  const buffer = readFileSync(path);
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
}

test(
  "documented real Phase C binary projects using a real original COLMAP source pose",
  {
    skip: available ? false : "The optional documented Phase B/C artifacts are not on this machine",
  },
  (t) => {
    const data = parseGaussianSplat(arrayBuffer(splatPath), arrayBuffer(sidecarPath), 37801);
    const pose = readFileSync(posesPath, "utf8")
      .split(/\r?\n/)
      .find((line) => line && !line.startsWith("#"))
      .trim()
      .split(/\s+/);
    const cameraId = pose[8];
    const intrinsics = readFileSync(camerasPath, "utf8")
      .split(/\r?\n/)
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => line.trim().split(/\s+/))
      .find((line) => line[0] === cameraId);
    assert.equal(intrinsics[1], "PINHOLE");
    const [width, height, fx, fy, cx, cy] = intrinsics.slice(2).map(Number);
    const [w, x, y, z, tx, ty, tz] = pose.slice(1, 8).map(Number);
    const colmapView = new Matrix4()
      .makeRotationFromQuaternion(new Quaternion(x, y, z, w).normalize())
      .setPosition(tx, ty, tz);
    const view = new Matrix4().makeScale(1, -1, -1).multiply(colmapView);
    const camera = new PerspectiveCamera(
      (2 * Math.atan(height / (2 * fy)) * 180) / Math.PI,
      width / height,
      0.0001,
      10000,
    );
    // Use the exact source intrinsics to independently check the projector's center math.
    camera.projectionMatrix.elements[0] = (2 * fx) / width;
    camera.projectionMatrix.elements[5] = (2 * fy) / height;
    camera.projectionMatrix.elements[8] = 1 - (2 * cx) / width;
    camera.projectionMatrix.elements[9] = (2 * cy) / height - 1;
    const out = new Float64Array(7);
    const order = sortGaussiansBackToFront(data.positions, view.elements);
    let visible = 0,
      anisotropic = 0,
      partialAlpha = 0;
    const begin = performance.now();
    for (const index of order) {
      if (
        !projectGaussian(
          data,
          index,
          view.elements,
          camera.projectionMatrix.elements,
          width,
          height,
          camera.near,
          camera.far,
          out,
        )
      )
        continue;
      visible++;
      const major = Math.hypot(out[3] * width, out[4] * height);
      const minor = Math.hypot(out[5] * width, out[6] * height);
      if (major / minor > 1.1) anisotropic++;
      if (data.colors[index * 4 + 3] > 0 && data.colors[index * 4 + 3] < 1) partialAlpha++;
      const m = colmapView.elements,
        p = index * 3;
      const px = data.positions[p],
        py = data.positions[p + 1],
        pz = data.positions[p + 2];
      const X = m[0] * px + m[4] * py + m[8] * pz + m[12];
      const Y = m[1] * px + m[5] * py + m[9] * pz + m[13];
      const Z = m[2] * px + m[6] * py + m[10] * pz + m[14];
      assert.ok(Math.abs(((out[0] + 1) * width) / 2 - ((fx * X) / Z + cx)) < 1e-7);
      assert.ok(Math.abs(((1 - out[1]) * height) / 2 - ((fy * Y) / Z + cy)) < 1e-7);
    }
    assert.ok(visible > 1000);
    assert.ok(anisotropic > visible / 2);
    assert.ok(partialAlpha > visible / 2);
    t.diagnostic(
      `${data.count} real Gaussians; ${visible} visible from ${pose[9]}; ${anisotropic} anisotropic; projection/check loop ${(performance.now() - begin).toFixed(1)}ms (not a browser FPS benchmark).`,
    );
  },
);
