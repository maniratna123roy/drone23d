import { create } from "zustand";
import type {
  VantageCamCapture,
  VantageCamEvent,
  VantageCamQualityReport,
  VantageCamUIState,
} from "@/types/vantagecam";

export interface VantageCamStore extends VantageCamUIState {
  // Capture management
  addCapture: (capture: VantageCamCapture) => void;
  setCurrentCaptureId: (id: string | null) => void;
  updateCapture: (id: string, updates: Partial<VantageCamCapture>) => void;

  // Event streaming
  addEvent: (event: VantageCamEvent) => void;
  clearEvents: () => void;
  getEventsByType: (type: string) => VantageCamEvent[];
  getCurrentProgress: () => number;

  // Quality report
  setQualityReport: (report: VantageCamQualityReport) => void;
  clearQualityReport: () => void;

  // Connection state
  setConnected: (connected: boolean) => void;
  setError: (error: string | null) => void;

  // Bulk operations
  reset: () => void;
}

const initialState: VantageCamUIState = {
  captures: [],
  currentCaptureId: null,
  events: [],
  qualityReport: null,
  isConnected: false,
  error: null,
};

export const useVantageCamStore = create<VantageCamStore>((set, get) => ({
  ...initialState,

  // Capture management
  addCapture: (capture) =>
    set((state) => ({
      captures: [...state.captures, capture],
    })),

  setCurrentCaptureId: (id) =>
    set({
      currentCaptureId: id,
      events: [], // Clear events when switching captures
      qualityReport: null,
    }),

  updateCapture: (id, updates) =>
    set((state) => ({
      captures: state.captures.map((cap) =>
        cap.capture_id === id ? { ...cap, ...updates } : cap
      ),
    })),

  // Event streaming
  addEvent: (event) =>
    set((state) => ({
      events: [...state.events, event],
    })),

  clearEvents: () => set({ events: [] }),

  getEventsByType: (type) => {
    const { events } = get();
    return events.filter((e) => e.type === type);
  },

  getCurrentProgress: () => {
    const { events } = get();
    // Return the latest progress value from stage_progress or stage_complete events
    let maxProgress = 0;
    for (const event of events) {
      if (
        (event.type === "stage_progress" || event.type === "stage_complete") &&
        event.progress !== undefined
      ) {
        maxProgress = Math.max(maxProgress, event.progress);
      }
    }
    return maxProgress;
  },

  // Quality report
  setQualityReport: (report) => set({ qualityReport: report }),
  clearQualityReport: () => set({ qualityReport: null }),

  // Connection state
  setConnected: (connected) => set({ isConnected: connected }),
  setError: (error) => set({ error }),

  // Bulk operations
  reset: () => set(initialState),
}));
