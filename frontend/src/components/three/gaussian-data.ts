/** The standard 32-byte export: XYZ, positive XYZ scale, RGBA, quantized WXYZ. */
export interface GaussianData {
  count: number;
  positions: Float32Array;
  scales: Float32Array;
  rotations: Float32Array;
  colors: Float32Array;
  /** Symmetric covariance entries xx, xy, xz, yy, yz, zz, in source coordinates. */
  covariance: Float64Array;
  classes: Uint8Array;
}

export function parseGaussianSplat(
  buffer: ArrayBuffer,
  classesBuffer: ArrayBuffer,
  expectedCount: number,
  classified = false,
): GaussianData {
  if (!Number.isSafeInteger(expectedCount) || expectedCount <= 0) {
    throw new Error("The manifest must declare a positive Gaussian count.");
  }
  if (buffer.byteLength !== expectedCount * 32) {
    throw new Error(
      `Invalid .splat length: expected ${expectedCount * 32} bytes, received ${buffer.byteLength}.`,
    );
  }
  if (classesBuffer.byteLength !== expectedCount) {
    throw new Error("The class sidecar must contain exactly one byte per Gaussian.");
  }
  const classes = new Uint8Array(classesBuffer);
  const positions = new Float32Array(expectedCount * 3);
  const scales = new Float32Array(expectedCount * 3);
  const rotations = new Float32Array(expectedCount * 4);
  const colors = new Float32Array(expectedCount * 4);
  const covariance = new Float64Array(expectedCount * 6);
  const view = new DataView(buffer);

  for (let i = 0; i < expectedCount; i++) {
    if (![0, 1, 2, 3, 255].includes(classes[i]!)) {
      throw new Error(`Gaussian ${i}: invalid semantic class ID.`);
    }
    if (!classified && classes[i] !== 255) {
      throw new Error(`Gaussian ${i}: this UNKNOWN-semantics scene requires class 255.`);
    }
    const offset = i * 32;
    for (let axis = 0; axis < 3; axis++) {
      const position = view.getFloat32(offset + axis * 4, true);
      const scale = view.getFloat32(offset + 12 + axis * 4, true);
      if (!Number.isFinite(position) || !Number.isFinite(scale) || scale <= 0) {
        throw new Error(`Gaussian ${i}: positions must be finite and scales must be positive.`);
      }
      positions[i * 3 + axis] = position;
      scales[i * 3 + axis] = scale;
    }
    for (let channel = 0; channel < 4; channel++) {
      colors[i * 4 + channel] = view.getUint8(offset + 24 + channel) / 255;
    }
    let w = (view.getUint8(offset + 28) - 128) / 128;
    let x = (view.getUint8(offset + 29) - 128) / 128;
    let y = (view.getUint8(offset + 30) - 128) / 128;
    let z = (view.getUint8(offset + 31) - 128) / 128;
    const norm = Math.hypot(w, x, y, z);
    if (norm === 0) throw new Error(`Gaussian ${i}: zero-length WXYZ quaternion.`);
    w /= norm;
    x /= norm;
    y /= norm;
    z /= norm;
    rotations.set([w, x, y, z], i * 4);

    // R diag(scale²) Rᵀ; never rotate/normalize the COLMAP positions themselves.
    const r00 = 1 - 2 * (y * y + z * z),
      r01 = 2 * (x * y - w * z),
      r02 = 2 * (x * z + w * y);
    const r10 = 2 * (x * y + w * z),
      r11 = 1 - 2 * (x * x + z * z),
      r12 = 2 * (y * z - w * x);
    const r20 = 2 * (x * z - w * y),
      r21 = 2 * (y * z + w * x),
      r22 = 1 - 2 * (x * x + y * y);
    const sx = scales[i * 3]! ** 2,
      sy = scales[i * 3 + 1]! ** 2,
      sz = scales[i * 3 + 2]! ** 2;
    covariance.set(
      [
        r00 * r00 * sx + r01 * r01 * sy + r02 * r02 * sz,
        r00 * r10 * sx + r01 * r11 * sy + r02 * r12 * sz,
        r00 * r20 * sx + r01 * r21 * sy + r02 * r22 * sz,
        r10 * r10 * sx + r11 * r11 * sy + r12 * r12 * sz,
        r10 * r20 * sx + r11 * r21 * sy + r12 * r22 * sz,
        r20 * r20 * sx + r21 * r21 * sy + r22 * r22 * sz,
      ],
      i * 6,
    );
  }
  return { count: expectedCount, positions, scales, rotations, colors, covariance, classes };
}

/** Three.js matrices use column-major storage. More negative view Z is farther away. */
export function sortGaussiansBackToFront(
  positions: Float32Array,
  modelView: ArrayLike<number>,
  order = new Uint32Array(positions.length / 3),
  depths = new Float64Array(order.length),
): Uint32Array {
  for (let i = 0; i < order.length; i++) {
    order[i] = i;
    depths[i] =
      modelView[2]! * positions[i * 3]! +
      modelView[6]! * positions[i * 3 + 1]! +
      modelView[10]! * positions[i * 3 + 2]! +
      modelView[14]!;
  }
  order.sort((a, b) => depths[a]! - depths[b]! || a - b);
  return order;
}

/**
 * Project the actual 3D covariance through the perspective Jacobian.
 * Writes NDC center XYZ and two 3-sigma ellipse axes XY to `out` (seven values).
 * The renderer and native tests use this same path; no circular point-size fallback.
 */
export function projectGaussian(
  data: GaussianData,
  index: number,
  modelView: ArrayLike<number>,
  projection: ArrayLike<number>,
  width: number,
  height: number,
  near: number,
  far: number,
  out: Float64Array,
): boolean {
  const p = index * 3;
  const px = data.positions[p]!,
    py = data.positions[p + 1]!,
    pz = data.positions[p + 2]!;
  const x = modelView[0]! * px + modelView[4]! * py + modelView[8]! * pz + modelView[12]!;
  const y = modelView[1]! * px + modelView[5]! * py + modelView[9]! * pz + modelView[13]!;
  const z = modelView[2]! * px + modelView[6]! * py + modelView[10]! * pz + modelView[14]!;
  const depth = -z;
  if (
    depth <= near ||
    depth >= far ||
    width <= 0 ||
    height <= 0 ||
    data.colors[index * 4 + 3]! < 1 / 255
  )
    return false;

  const fx = (projection[0]! * width) / 2,
    fy = (projection[5]! * height) / 2;
  // Match the trainer's EWA field-of-view bound: far-off-axis linearization
  // must not turn a near-camera point into a viewport-sized ellipse. Keep the
  // projected mean unchanged so those offscreen centers are still culled.
  const marginX = 1.3 / projection[0]!,
    marginY = 1.3 / projection[5]!;
  const xOverDepth = Math.max(-marginX, Math.min(marginX, x / depth)),
    yOverDepth = Math.max(-marginY, Math.min(marginY, y / depth));
  const jx = fx / depth,
    jxz = (fx * xOverDepth) / depth;
  const jy = fy / depth,
    jyz = (fy * yOverDepth) / depth;
  // J R, so the unmodified source-frame covariance can be used directly.
  const ax = jx * modelView[0]! + jxz * modelView[2]!;
  const ay = jx * modelView[4]! + jxz * modelView[6]!;
  const az = jx * modelView[8]! + jxz * modelView[10]!;
  const bx = jy * modelView[1]! + jyz * modelView[2]!;
  const by = jy * modelView[5]! + jyz * modelView[6]!;
  const bz = jy * modelView[9]! + jyz * modelView[10]!;
  const c = index * 6;
  const xx = data.covariance[c]!,
    xy = data.covariance[c + 1]!,
    xz = data.covariance[c + 2]!;
  const yy = data.covariance[c + 3]!,
    yz = data.covariance[c + 4]!,
    zz = data.covariance[c + 5]!;
  const caX = xx * ax + xy * ay + xz * az,
    caY = xy * ax + yy * ay + yz * az,
    caZ = xz * ax + yz * ay + zz * az;
  const cbX = xx * bx + xy * by + xz * bz,
    cbY = xy * bx + yy * by + yz * bz,
    cbZ = xz * bx + yz * by + zz * bz;
  // gsplat's classic rasterizer uses a 0.3 pixel² low-pass term.
  const a = ax * caX + ay * caY + az * caZ + 0.3;
  const b = ax * cbX + ay * cbY + az * cbZ;
  const d = bx * cbX + by * cbY + bz * cbZ + 0.3;
  const mid = (a + d) / 2,
    radius = Math.hypot((a - d) / 2, b);
  const major = 3 * Math.sqrt(Math.max(0.3, mid + radius));
  const minor = 3 * Math.sqrt(Math.max(0.3, mid - radius));
  const angle = 0.5 * Math.atan2(2 * b, a - d);
  const cos = Math.cos(angle),
    sin = Math.sin(angle);
  out[0] = (projection[0]! * x + projection[8]! * z + projection[12]!) / depth;
  out[1] = (projection[5]! * y + projection[9]! * z + projection[13]!) / depth;
  out[2] = (projection[10]! * z + projection[14]!) / depth;
  out[3] = (major * cos * 2) / width;
  out[4] = (major * sin * 2) / height;
  out[5] = (-minor * sin * 2) / width;
  out[6] = (minor * cos * 2) / height;
  if (!out.every(Number.isFinite)) return false;
  const extentX = Math.abs(out[3]!) + Math.abs(out[5]!);
  const extentY = Math.abs(out[4]!) + Math.abs(out[6]!);
  return Math.abs(out[0]!) <= 1 + extentX && Math.abs(out[1]!) <= 1 + extentY;
}

/** Same alpha profile/cutoffs used in the quad fragment shader. */
export function gaussianAlpha(opacity: number, sigmaX: number, sigmaY: number): number {
  const radiusSquared = sigmaX * sigmaX + sigmaY * sigmaY;
  if (radiusSquared > 9) return 0;
  const alpha = Math.min(0.99, opacity * Math.exp(-0.5 * radiusSquared));
  return alpha < 1 / 255 ? 0 : alpha;
}
