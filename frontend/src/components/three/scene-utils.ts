/** Shared constants + helpers for the procedural spatial scenes. */

/** Palette mirrors the CSS design tokens (WebGL cannot read CSS variables). */
export const SCENE_COLORS = {
  background: "#10231f",
  point: "#70847b",
  pointAccent: "#83dcc4",
  accent: "#75cfb6",
  accentDim: "#356c60",
  building: "#213b35",
  buildingEdge: "#647d72",
  road: "#344c46",
  vegetation: "#3f6756",
  infrastructure: "#49645d",
} as const;

/** Metres per scene unit. Keeps mock spatial data readable in the UI. */
export const M_PER_UNIT = 12;

/** Smooth procedural heightfield used by terrain, points and object bases. */
export function terrainHeight(x: number, z: number): number {
  return (
    1.15 * Math.sin(x * 0.24) * Math.cos(z * 0.29) +
    0.55 * Math.sin(x * 0.11 + z * 0.17) +
    0.25 * Math.cos(x * 0.53 - z * 0.41)
  );
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

/** Cheap deterministic hash → [0,1) */
export function hash(n: number): number {
  const s = Math.sin(n * 127.1) * 43758.5453;
  return s - Math.floor(s);
}
