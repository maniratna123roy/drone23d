import test from "node:test";
import assert from "node:assert/strict";
import {
  createVerifiedPipelineApi,
  parseVerifiedScene,
  parsePipelineStatus,
  validateVideo,
} from "../src/lib/verifiedPipeline.ts";
import { VerifiedPipelineSession } from "../src/lib/verifiedPipelineSession.ts";
import { parseGaussianSplat } from "../src/components/three/gaussian-data.ts";
import { manifest, status, binary, classes } from "./verified-fixtures.mjs";

const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
function fixtureApi(overrides = {}) {
  return {
    scene: async () => ({ status: "empty", manifest: null }),
    status: async () => status(),
    assets: async () => parseGaussianSplat(binary(), classes(), 1),
    upload: async () => ({ job_id: "new-job", status: "processing", message: "Accepted" }),
    ...overrides,
  };
}
async function sessionFixture(t, overrides = {}) {
  const api = fixtureApi(overrides);
  const changes = [];
  const session = new VerifiedPipelineSession(api, (state) => changes.push(state));
  t.after(() => session.stop());
  session.start(60000);
  await session.refresh();
  await tick();
  return { session, api, changes };
}

test("accepts only a versioned verified manifest or an explicit empty response", () => {
  assert.deepEqual(parseVerifiedScene({ status: "empty", manifest: null }), {
    status: "empty",
    manifest: null,
  });
  assert.equal(
    parseVerifiedScene({ status: "ready", manifest: manifest() }).manifest.coordinate_frame,
    "COLMAP_PHASE_A",
  );
  for (const change of [
    { splat_url: "/static/scene.splat" },
    { classes_url: "https://other.invalid/classes" },
    { job_id: "../escape" },
    { version: "" },
    { gaussian_count: 0 },
    { gaussian_count: 1.2 },
    { coordinate_frame: "Z_UP_METRES" },
    { scale_status: "METRIC" },
    { semantics: "BUILDINGS" },
    { capabilities: { queries: true, edits: false } },
    { schema_version: 2 },
    { created_at: "not-a-date" },
    { quality: null },
  ])
    assert.throws(() =>
      parseVerifiedScene({ status: "ready", manifest: { ...manifest(), ...change } }),
    );
  assert.throws(() => parseVerifiedScene({ status: "empty", manifest: manifest() }));
  assert.throws(() => parseVerifiedScene({ status: "ready", manifest: null }));
});

test("validates source camera and bounds without requiring a fabricated ground/up-axis", () => {
  const base = manifest();
  for (const change of [
    { position: [NaN, 0, 0] },
    { target: base.camera.position },
    { up: [0, 0, 0] },
    { up: [0, 0, 1] },
    { near: 0 },
    { far: 0.01 },
    { fov_y_degrees: 180 },
  ]) {
    assert.throws(
      () =>
        parseVerifiedScene({
          status: "ready",
          manifest: { ...base, camera: { ...base.camera, ...change } },
        }),
      /camera/,
    );
  }
  const arbitrary = { ...base, camera: { ...base.camera, up: [1, 2, 0] } };
  assert.deepEqual(
    parseVerifiedScene({ status: "ready", manifest: arbitrary }).manifest.camera.up,
    [1, 2, 0],
  );
  assert.throws(
    () =>
      parseVerifiedScene({
        status: "ready",
        manifest: { ...base, bounds: { min: [2, 2, 2], max: [1, 1, 1] } },
      }),
    /bounds/,
  );
});

test("status and local-video input validation reject malformed state and empty files", () => {
  assert.equal(parsePipelineStatus(status("error", "job-a")).error, "Geometry verification failed");
  for (const value of [
    { ...status(), progress: NaN },
    { ...status(), progress: 101 },
    status("completed"),
    { ...status(), details: null },
  ])
    assert.throws(() => parsePipelineStatus(value));
  validateVideo({ name: "flight.MP4", size: 10 });
  assert.throws(() => validateVideo({ name: "scene.splat", size: 10 }), /video/);
  assert.throws(() => validateVideo({ name: "flight.mov", size: 0 }), /empty/);
});

test("real transport uses only pipeline endpoints and immutable manifest files, honoring abort", async () => {
  const calls = [];
  const m = manifest();
  const controller = new AbortController();
  const api = createVerifiedPipelineApi("http://local.invalid/", async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith("/scene")) return Response.json({ status: "ready", manifest: m });
    if (url.includes("/status")) return Response.json(status("completed", m.job_id));
    if (url.endsWith("/upload")) {
      assert.equal(options.body.get("file").name, "test.mp4");
      return Response.json({ job_id: m.job_id, status: "processing", message: "Accepted" });
    }
    return new Response(url.endsWith(".splat") ? binary() : classes());
  });
  await api.scene(controller.signal);
  await api.status(controller.signal, "job with spaces");
  await api.upload(new File(["video"], "test.mp4"), controller.signal);
  const data = await api.assets(m, controller.signal);
  assert.equal(data.count, 1);
  assert.equal(data.colors[3], Math.fround(128 / 255));
  assert.ok(calls.every((call) => call.options.signal === controller.signal));
  assert.match(calls[1].url, /job_id=job%20with%20spaces/);
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(calls[3].url, `http://local.invalid${m.splat_url}`);
  assert.equal(calls[4].url, `http://local.invalid${m.classes_url}`);
  assert.ok(calls.every((call) => !/objects|kaggle|\/static\/scene\./.test(call.url)));
  controller.abort();
  await assert.rejects(api.assets(m, controller.signal), /cancelled/);
});

test("FastAPI detail errors stay friendly for upload/status/scene/asset failures", async () => {
  const api = createVerifiedPipelineApi("", async () =>
    Response.json({ detail: "Another local job is running" }, { status: 409 }),
  );
  const signal = new AbortController().signal;
  for (const action of [
    () => api.scene(signal),
    () => api.status(signal),
    () => api.assets(manifest(), signal),
    () => api.upload(new File(["x"], "test.mp4"), signal),
  ]) {
    await assert.rejects(action(), /Another local job is running/);
  }
});

test("reload discovers durable processing/error status; empty never loads any scene", async (t) => {
  let loads = 0;
  const { session, api } = await sessionFixture(t, {
    status: async () => status("processing", "existing-job"),
    assets: async () => {
      loads++;
      throw new Error("unexpected");
    },
  });
  assert.equal(session.state.status.job_id, "existing-job");
  assert.equal(session.state.displayed, null);
  assert.equal(loads, 0);
  api.status = async () => status("error", "existing-job");
  await session.refresh();
  assert.equal(session.state.status.error, "Geometry verification failed");
  assert.equal(session.state.displayed, null);
  await session.refresh();
  assert.equal(
    session.state.status.error,
    "Geometry verification failed",
    "failure must not disappear on a timer",
  );
});

test("completed status alone cannot load legacy/static or unpublished assets", async (t) => {
  let loads = 0;
  const { session } = await sessionFixture(t, {
    status: async () => status("completed", "job-a"),
    assets: async () => {
      loads++;
      throw new Error("unexpected");
    },
  });
  assert.equal(session.state.displayed, null);
  assert.equal(loads, 0);
});

test("a later failed job preserves and identifies the previous verified scene", async (t) => {
  const previous = manifest("previous-job");
  const { session, api } = await sessionFixture(t, {
    scene: async () => ({ status: "ready", manifest: previous }),
    status: async () => status("completed", previous.job_id),
  });
  const displayed = session.state.displayed;
  assert.equal(displayed.manifest.job_id, previous.job_id);
  api.status = async () => status("error", "later-job");
  await session.refresh();
  await tick();
  assert.equal(session.state.displayed, displayed);
  assert.notEqual(session.state.status.job_id, displayed.manifest.job_id);
  assert.equal(session.state.status.status, "error");
});

test("malformed latest files never replace the successful scene; manual retry can recover", async (t) => {
  const { session, api } = await sessionFixture(t, {
    scene: async () => ({ status: "ready", manifest: manifest("old") }),
  });
  const displayed = session.state.displayed;
  let attempts = 0;
  api.scene = async () => ({ status: "ready", manifest: manifest("new") });
  api.assets = async () => {
    attempts++;
    return parseGaussianSplat(new ArrayBuffer(31), classes(), 1);
  };
  await session.refresh();
  await tick();
  assert.equal(session.state.displayed, displayed);
  assert.match(session.state.assetError, /length/);
  await session.refresh();
  await tick();
  assert.equal(attempts, 1, "do not hammer a broken immutable file every poll");
  api.assets = fixtureApi().assets;
  await session.refresh(true);
  await tick();
  assert.equal(session.state.displayed.manifest.job_id, "new");
  assert.equal(session.state.assetError, null);
});

test("late asset responses cannot overwrite a newer manifest and explicit empty removes old content", async (t) => {
  const old = deferred();
  const { session, api } = await sessionFixture(t, {
    scene: async () => ({ status: "ready", manifest: manifest("old") }),
    assets: () => old.promise,
  });
  assert.equal(session.state.displayed, null);
  assert.equal(session.state.loadingAssets, true);
  api.scene = async () => ({ status: "ready", manifest: manifest("new") });
  api.assets = fixtureApi().assets;
  await session.refresh();
  await tick();
  assert.equal(session.state.displayed.manifest.job_id, "new");
  old.resolve(await fixtureApi().assets());
  await tick();
  assert.equal(session.state.displayed.manifest.job_id, "new");
  api.scene = fixtureApi().scene;
  await session.refresh();
  assert.equal(session.state.displayed, null);
  assert.equal(session.state.manifest, null);
});

test("polling errors retain the last known scene/status and remain visible until explicit retry", async (t) => {
  const { session, api } = await sessionFixture(t, {
    scene: async () => ({ status: "ready", manifest: manifest() }),
    status: async () => status("error", "failed"),
  });
  const previous = session.state.displayed;
  api.status = async () => {
    throw new Error("Connection lost");
  };
  await session.refresh();
  assert.match(session.state.connectionError, /Connection lost/);
  assert.equal(session.state.displayed, previous);
  assert.equal(session.state.status.status, "error");
  api.status = async () => status("error", "failed");
  await session.refresh();
  assert.match(session.state.connectionError, /Connection lost/);
  await session.refresh(true);
  assert.equal(session.state.connectionError, null);
});

test("upload acceptance is visible immediately; errors are durable and repeat selection works", async (t) => {
  const { session, api } = await sessionFixture(t);
  api.upload = async () => {
    throw new Error("Video verification could not start");
  };
  await session.upload(new File(["video"], "flight.mp4"));
  await tick();
  assert.match(session.state.uploadError, /could not start/);
  await session.refresh();
  assert.match(session.state.uploadError, /could not start/);
  api.upload = fixtureApi().upload;
  api.status = async () => status("processing", "new-job");
  await session.upload(new File(["video"], "flight.mp4"));
  await tick();
  assert.equal(session.state.status.job_id, "new-job");
  assert.equal(session.state.uploadError, null);
});

test("stop aborts outstanding requests and ignores late completions (unmount cleanup)", async (t) => {
  const pending = deferred();
  let assetSignal;
  const { session, changes } = await sessionFixture(t, {
    scene: async () => ({ status: "ready", manifest: manifest() }),
    assets: (_, signal) => {
      assetSignal = signal;
      return pending.promise;
    },
  });
  session.stop();
  assert.equal(assetSignal.aborted, true);
  const count = changes.length;
  pending.resolve(await fixtureApi().assets());
  await tick();
  assert.equal(changes.length, count);
  assert.equal(session.state.displayed, null);
});
