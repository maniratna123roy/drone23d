import test from "node:test";
import assert from "node:assert/strict";
import { parseGaussianSplat } from "../src/components/three/gaussian-data.ts";
import { semanticCounts, semanticColor } from "../src/components/three/semantic-display.ts";
import { parseVerifiedScene } from "../src/lib/verifiedPipeline.ts";
import { binary, manifest } from "./verified-fixtures.mjs";

test("classified sidecars preserve row order and reject invalid IDs", () => {
  const sidecar = new Uint8Array([0, 1, 2, 3, 255]).buffer;
  const data = parseGaussianSplat(binary([{}, {}, {}, {}, {}]), sidecar, 5, true);
  assert.deepEqual([...data.classes], [0, 1, 2, 3, 255]);
  assert.deepEqual(semanticCounts(data.classes), {0: 1, 1: 1, 2: 1, 3: 1, 255: 1});
  assert.deepEqual(semanticColor(0), [245, 158, 11]);
  assert.throws(() => parseGaussianSplat(binary(), new Uint8Array([4]).buffer, 1, true), /invalid semantic/);
  assert.throws(() => parseGaussianSplat(binary(), new Uint8Array([0]).buffer, 1), /UNKNOWN/);
});

test("multi-view metadata validates counts and does not enable metric editing", () => {
  const m = {...manifest(), semantics: "CLASSIFIED_MULTIVIEW", gaussian_count: 3,
    classification: {method: "SEGFORMER_DEPTH_VISIBLE_MULTIVIEW", class_counts: {structure: 1, terrain: 0, road: 1, vegetation: 0, unknown: 1}, views: 3, classified_fraction: 2 / 3}};
  assert.equal(parseVerifiedScene({status: "ready", manifest: m}).manifest.semantics, "CLASSIFIED_MULTIVIEW");
  assert.throws(() => parseVerifiedScene({status: "ready", manifest: {...m, capabilities: {queries: true, edits: true}}}), /classification/);
  assert.throws(() => parseVerifiedScene({status: "ready", manifest: {...m, gaussian_count: 4}}), /classification/);
});
