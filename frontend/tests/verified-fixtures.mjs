export function manifest(job = "verified-job-1") {
  return {
    schema_version: 1,
    job_id: job,
    version: `${job}-v1`,
    source_name: "local-drone.mp4",
    created_at: "2026-10-02T12:00:00Z",
    splat_url: `/static/scenes/${job}/scene.splat`,
    classes_url: `/static/scenes/${job}/scene.classes.u8`,
    gaussian_count: 1,
    coordinate_frame: "COLMAP_PHASE_A",
    scale_status: "RELATIVE_UNCALIBRATED",
    semantics: "UNKNOWN",
    capabilities: { queries: false, edits: false },
    bounds: { min: [-1, -1, -12], max: [1, 1, -8] },
    camera: {
      position: [0, 0, 0],
      target: [0, 0, -10],
      up: [0, 1, 0],
      fov_y_degrees: 60,
      near: 0.1,
      far: 100,
    },
    quality: { passed: true },
  };
}
export function status(state = "idle", jobId = null) {
  return {
    job_id: jobId,
    status: state,
    step: state,
    progress: state === "completed" ? 100 : 0,
    details: {},
    error: state === "error" ? "Geometry verification failed" : null,
  };
}
export function binary(rows = [{}]) {
  const buffer = new ArrayBuffer(rows.length * 32);
  const view = new DataView(buffer);
  rows.forEach((row, i) => {
    const {
      position = [0, 0, -10],
      scale = [2, 1, 0.5],
      color = [200, 100, 50, 128],
      quaternion = [1, 0, 0, 0],
    } = row;
    [...position, ...scale].forEach((v, axis) => view.setFloat32(i * 32 + axis * 4, v, true));
    color.forEach((v, channel) => view.setUint8(i * 32 + 24 + channel, v));
    quaternion.forEach((v, channel) =>
      view.setUint8(i * 32 + 28 + channel, Math.max(0, Math.min(255, Math.floor(v * 128 + 128)))),
    );
  });
  return buffer;
}
export function classes(count = 1) {
  return new Uint8Array(count).fill(255).buffer;
}
