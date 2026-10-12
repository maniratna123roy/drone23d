/** Same IDs and colors as the offline classifier; unknown always has its own control. */
export const SEMANTIC_CLASSES = [
  { id: 0, label: "Structure", color: [245, 158, 11] },
  { id: 1, label: "Terrain", color: [168, 116, 72] },
  { id: 2, label: "Road / sidewalk", color: [90, 160, 240] },
  { id: 3, label: "Vegetation", color: [40, 210, 100] },
  { id: 255, label: "Unknown", color: [110, 110, 120] },
] as const;

export function semanticCounts(classes: Uint8Array): Record<number, number> {
  const counts: Record<number, number> = { 0: 0, 1: 0, 2: 0, 3: 0, 255: 0 };
  for (const id of classes) counts[id] = (counts[id] ?? 0) + 1;
  return counts;
}

export function semanticColor(id: number): readonly number[] {
  return (SEMANTIC_CLASSES.find((item) => item.id === id) ?? SEMANTIC_CLASSES[4]).color;
}
