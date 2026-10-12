import { create } from "zustand";
import type { LayerId, SpatialObject } from "@/types/spatial";

export interface SpatialStore {
  // Scene state
  sceneVersion: number;
  objects: SpatialObject[];
  setObjects: (objects: SpatialObject[]) => void;
  updateSceneVersion: () => void;

  // Selection state
  selectedObjectId: string | null;
  setSelectedObjectId: (id: string | null) => void;
  hoveredObjectId: string | null;
  setHoveredObjectId: (id: string | null) => void;
  getSelectedObject: () => SpatialObject | undefined;

  // Layer visibility state
  layerVisibility: Record<LayerId, boolean>;
  toggleLayer: (layerId: LayerId) => void;
  setLayerVisibility: (layerId: LayerId, visible: boolean) => void;
  getVisibleObjects: () => SpatialObject[];

  // Layer opacity
  layerOpacity: Record<LayerId, number>;
  setLayerOpacity: (layerId: LayerId, opacity: number) => void;

  // Solo mode
  soloLayerId: LayerId | null;
  setSoloLayer: (layerId: LayerId | null) => void;

  // Undo/Redo
  undoStack: SpatialObject[][] | [];
  redoStack: SpatialObject[][] | [];
  pushUndo: () => void;
  undo: () => void;
  redo: () => void;

  // Query results
  highlightedObjectIds: string[];
  setHighlightedObjectIds: (ids: string[]) => void;
  queryFilterActive: boolean;
  setQueryFilterActive: (active: boolean) => void;

  // Phase 7: Ghost Preview & Selective Masking
  ghostObjects: import("@/types/spatial").GhostObject[];
  setGhostObjects: (ghosts: import("@/types/spatial").GhostObject[]) => void;
  clearGhostObjects: () => void;
  previewToken: string | null;
  setPreviewToken: (token: string | null) => void;
  hiddenBboxes: Array<{ min_x: number; max_x: number; min_y: number; max_y: number }>;
  setHiddenBboxes: (bboxes: Array<{ min_x: number; max_x: number; min_y: number; max_y: number }>) => void;
  addHiddenBbox: (bbox: { min_x: number; max_x: number; min_y: number; max_y: number }) => void;

  // Camera state
  cameraPosition: [number, number, number];
  cameraTarget: [number, number, number];
  setCameraPosition: (pos: [number, number, number]) => void;
  setCameraTarget: (target: [number, number, number]) => void;
}

export const useSpatialStore = create<SpatialStore>((set, get) => ({
  // Scene state
  sceneVersion: 0,
  objects: [],
  setObjects: (objects) => set({ objects }),
  updateSceneVersion: () => set((state) => ({ sceneVersion: state.sceneVersion + 1 })),

  // Selection state
  selectedObjectId: null,
  setSelectedObjectId: (id) => set({ selectedObjectId: id }),
  hoveredObjectId: null,
  setHoveredObjectId: (id) => set({ hoveredObjectId: id }),
  getSelectedObject: () => {
    const { selectedObjectId, objects } = get();
    return objects.find((obj) => obj.id === selectedObjectId);
  },

  // Layer visibility state
  layerVisibility: {
    buildings: true,
    roads: true,
    terrain: true,
    vegetation: true,
    infrastructure: true,
  },
  toggleLayer: (layerId) => {
    set((state) => ({
      layerVisibility: {
        ...state.layerVisibility,
        [layerId]: !state.layerVisibility[layerId],
      },
    }));
  },
  setLayerVisibility: (layerId, visible) => {
    set((state) => ({
      layerVisibility: {
        ...state.layerVisibility,
        [layerId]: visible,
      },
    }));
  },
  getVisibleObjects: () => {
    const { objects, layerVisibility, soloLayerId } = get();
    if (soloLayerId) {
      return objects.filter((obj) => obj.layer === soloLayerId);
    }
    return objects.filter((obj) => layerVisibility[obj.layer]);
  },

  // Layer opacity
  layerOpacity: {
    buildings: 1,
    roads: 1,
    terrain: 1,
    vegetation: 1,
    infrastructure: 1,
  },
  setLayerOpacity: (layerId, opacity) => {
    set((state) => ({
      layerOpacity: {
        ...state.layerOpacity,
        [layerId]: Math.max(0, Math.min(1, opacity)),
      },
    }));
  },

  // Solo mode
  soloLayerId: null,
  setSoloLayer: (layerId) => set({ soloLayerId: layerId }),

  // Undo/Redo
  undoStack: [],
  redoStack: [],
  pushUndo: () => {
    const { objects, undoStack } = get();
    set({ undoStack: [...undoStack, objects], redoStack: [] });
  },
  undo: () => {
    const { undoStack, redoStack, objects } = get();
    if (undoStack.length === 0) return;
    const previous = undoStack[undoStack.length - 1];
    if (!previous) return;
    set({
      objects: previous,
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, objects],
    });
  },
  redo: () => {
    const { redoStack, undoStack, objects } = get();
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    if (!next) return;
    set({
      objects: next,
      redoStack: redoStack.slice(0, -1),
      undoStack: [...undoStack, objects],
    });
  },

  // Query results
  highlightedObjectIds: [],
  setHighlightedObjectIds: (ids) => set({ highlightedObjectIds: ids }),
  queryFilterActive: false,
  setQueryFilterActive: (active) => set({ queryFilterActive: active }),

  // Phase 7: Ghost Preview & Selective Masking
  ghostObjects: [],
  setGhostObjects: (ghosts) => set({ ghostObjects: ghosts }),
  clearGhostObjects: () => set({ ghostObjects: [], previewToken: null }),
  previewToken: null,
  setPreviewToken: (token) => set({ previewToken: token }),
  hiddenBboxes: [],
  setHiddenBboxes: (bboxes) => set({ hiddenBboxes: bboxes }),
  addHiddenBbox: (bbox) =>
    set((state) => ({
      hiddenBboxes: [...state.hiddenBboxes, bbox],
    })),

  // Camera state
  cameraPosition: [0, 7, 18],
  cameraTarget: [0, 0, 0],
  setCameraPosition: (pos) => set({ cameraPosition: pos }),
  setCameraTarget: (target) => set({ cameraTarget: target }),
}));
