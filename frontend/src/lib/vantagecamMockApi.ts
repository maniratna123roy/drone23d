/**
 * VantageCam Mock API
 *
 * Provides pre-seeded demo captures for the judge demo. When DEMO_MODE is enabled,
 * these mocks are served instead of real API calls. Simulates WebSocket progress
 * events with realistic timing.
 *
 * Analogy: Like a script for a theatrical performance—each "capture" is a pre-recorded
 * show that plays with realistic timing, so judges see what a real pipeline looks like
 * without waiting hours for actual processing.
 */

import type {
  VantageCamCapture,
  VantageCamEvent,
  VantageCamQualityReport,
} from "@/types/vantagecam";

// Enable demo mode for judge presentations
export const VANTAGECAM_DEMO_MODE = true;

/**
 * Pre-seeded demo captures
 * Each shows different tiers + real-looking timing
 */
export const DEMO_CAPTURES: VantageCamCapture[] = [
  {
    capture_id: "demo-001-standard",
    name: "Downtown Site A (Standard)",
    tier: "standard",
    status: "completed",
    created_at: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    updated_at: new Date(Date.now() - 3500000).toISOString(),
    progress_percent: 100,
    current_stage: null,
  },
  {
    capture_id: "demo-002-enhanced",
    name: "Harbor District (Enhanced)",
    tier: "enhanced",
    status: "completed",
    created_at: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
    updated_at: new Date(Date.now() - 6900000).toISOString(),
    progress_percent: 100,
    current_stage: null,
  },
  {
    capture_id: "demo-003-premium",
    name: "Central Business District (Premium)",
    tier: "premium",
    status: "processing",
    created_at: new Date(Date.now() - 1800000).toISOString(), // 30 min ago
    updated_at: new Date().toISOString(),
    progress_percent: 65,
    current_stage: "splats",
  },
];

/**
 * Generate demo events for a capture (simulating pipeline execution)
 * Realistic timing: ~2min for standard, ~4min for enhanced, ~6min for premium
 */
export function generateDemoEvents(captureId: string): VantageCamEvent[] {
  const capture = DEMO_CAPTURES.find((c) => c.capture_id === captureId);
  if (!capture) return [];

  // Duration varies by tier
  const durations: Record<string, number[]> = {
    standard: [1200, 3500, 2800, 8500, 12300, 5600, 7200, 4100, 2300, 1400], // total ~48.9s
    enhanced: [1500, 5200, 4100, 15000, 22000, 9800, 13000, 7500, 4200, 2100], // total ~84.5s
    premium: [2000, 7500, 6200, 22000, 32000, 15000, 19000, 11000, 6500, 3200], // total ~124.4s
  };

  const stageDurations =
    durations[capture.tier] || durations.standard;

  const stages: Array<"probe" | "frames" | "masking" | "sfm" | "dense" | "mesh" | "splats" | "georef" | "quality_gate" | "export"> = [
    "probe",
    "frames",
    "masking",
    "sfm",
    "dense",
    "mesh",
    "splats",
    "georef",
    "quality_gate",
    "export",
  ];

  const events: VantageCamEvent[] = [];
  let currentTime = 0;

  for (let stageIdx = 0; stageIdx < stages.length; stageIdx++) {
    const stageName = stages[stageIdx];
    const stageDuration = stageDurations[stageIdx];

    // Stage start
    events.push({
      type: "stage_start",
      capture_id: captureId,
      stage_index: stageIdx,
      stage_name: stageName,
      progress: (stageIdx * 10),
      timestamp: currentTime,
    });

    // Progress updates (25%, 50%, 75%)
    const progressIntervals = [
      stageDuration * 0.25,
      stageDuration * 0.5,
      stageDuration * 0.75,
    ];

    for (const interval of progressIntervals) {
      currentTime += Math.round(interval);
      events.push({
        type: "stage_progress",
        capture_id: captureId,
        stage_index: stageIdx,
        stage_name: stageName,
        progress: (stageIdx * 10) + (interval / stageDuration) * 10,
        timestamp: currentTime,
      });
    }

    // Stage complete
    currentTime += Math.round(stageDuration * 0.25);
    events.push({
      type: "stage_complete",
      capture_id: captureId,
      stage_index: stageIdx,
      stage_name: stageName,
      progress: ((stageIdx + 1) * 10),
      timestamp: currentTime,
      duration_ms: stageDuration,
    });

    // Status update every 2-3 stages
    if ((stageIdx + 1) % 2 === 0) {
      events.push({
        type: "status_update",
        capture_id: captureId,
        timestamp: currentTime,
        metadata: {
          processing_cores: 6,
          memory_mb: 3200,
        },
      });
    }
  }

  // Pipeline complete
  const totalDuration = currentTime + 1000;
  events.push({
    type: "pipeline_complete",
    capture_id: captureId,
    timestamp: totalDuration,
    metadata: {
      artifacts: ["scene.splat", "labels.npy", "scene_frame.json"],
      quality_metrics: {
        gaussian_count: capture.tier === "premium" ? 50000 : capture.tier === "enhanced" ? 40000 : 30000,
        splat_size_mb: capture.tier === "premium" ? 180 : capture.tier === "enhanced" ? 128 : 96,
        quality_score: capture.tier === "premium" ? 0.92 : capture.tier === "enhanced" ? 0.87 : 0.81,
        coverage_percent: capture.tier === "premium" ? 96 : capture.tier === "enhanced" ? 92 : 85,
      },
    },
  });

  return events;
}

/**
 * Generate demo quality report for a completed capture
 */
export function generateDemoQualityReport(
  captureId: string
): VantageCamQualityReport {
  const capture = DEMO_CAPTURES.find((c) => c.capture_id === captureId);
  if (!capture) {
    return {
      capture_id: captureId,
      verdict: "FAIL",
      total_duration_ms: 0,
      stage_durations: {
        probe: 0,
        frames: 0,
        masking: 0,
        sfm: 0,
        dense: 0,
        mesh: 0,
        splats: 0,
        georef: 0,
        quality_gate: 0,
        export: 0,
      },
      artifacts: [],
      metrics: {},
      error_logs: "Capture not found in demo data",
    };
  }

  const events = generateDemoEvents(captureId);
  const stageDurations: Record<string, number> = {
    probe: 0,
    frames: 0,
    masking: 0,
    sfm: 0,
    dense: 0,
    mesh: 0,
    splats: 0,
    georef: 0,
    quality_gate: 0,
    export: 0,
  };

  // Calculate stage durations from events
  for (const event of events) {
    if (event.type === "stage_complete" && event.stage_name) {
      stageDurations[event.stage_name] = event.duration_ms || 0;
    }
  }

  const totalDuration = Object.values(stageDurations).reduce((a, b) => a + b, 0);
  const completeEvent = events.find((e) => e.type === "pipeline_complete");

  return {
    capture_id: captureId,
    verdict: "PASS",
    total_duration_ms: totalDuration,
    stage_durations: stageDurations,
    artifacts: [
      {
        name: "scene.splat",
        size_bytes: (capture.tier === "premium" ? 180 : capture.tier === "enhanced" ? 128 : 96) * 1024 * 1024,
        created_at: capture.updated_at,
        url: `/api/vantagecam/captures/${captureId}/artifacts/scene.splat/download`,
      },
      {
        name: "labels.npy",
        size_bytes: capture.tier === "premium" ? 195000 : capture.tier === "enhanced" ? 156000 : 117000,
        created_at: capture.updated_at,
        url: `/api/vantagecam/captures/${captureId}/artifacts/labels.npy/download`,
      },
      {
        name: "scene_frame.json",
        size_bytes: 2048,
        created_at: capture.updated_at,
        url: `/api/vantagecam/captures/${captureId}/artifacts/scene_frame.json/download`,
      },
    ],
    metrics: {
      gaussian_count: capture.tier === "premium" ? 50000 : capture.tier === "enhanced" ? 40000 : 30000,
      splat_size_mb: capture.tier === "premium" ? 180 : capture.tier === "enhanced" ? 128 : 96,
      quality_score: capture.tier === "premium" ? 0.92 : capture.tier === "enhanced" ? 0.87 : 0.81,
      coverage_percent: capture.tier === "premium" ? 96 : capture.tier === "enhanced" ? 92 : 85,
    },
  };
}

/**
 * Mock API: get all captures
 */
export async function mockGetCaptures(): Promise<VantageCamCapture[]> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(DEMO_CAPTURES);
    }, 300);
  });
}

/**
 * Mock API: get single capture
 */
export async function mockGetCapture(
  captureId: string
): Promise<VantageCamCapture | null> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(DEMO_CAPTURES.find((c) => c.capture_id === captureId) || null);
    }, 100);
  });
}

/**
 * Mock API: simulate WebSocket progress
 * Returns a function that generates events over time
 */
export async function* mockWebSocketStream(
  captureId: string
): AsyncGenerator<VantageCamEvent> {
  const events = generateDemoEvents(captureId);
  const startTime = Date.now();

  for (const event of events) {
    // Wait until real time matches event timestamp
    const eventTimeMs = event.timestamp || 0;
    const elapsedMs = Date.now() - startTime;
    const waitMs = Math.max(0, eventTimeMs - elapsedMs);

    if (waitMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, waitMs));
    }

    yield event;
  }
}

/**
 * Mock API: create capture (returns one of the demo captures)
 */
export async function mockCreateCapture(formData: FormData): Promise<VantageCamCapture> {
  return new Promise((resolve) => {
    setTimeout(() => {
      // Return a new demo capture with slightly different ID
      const newId = `demo-new-${Date.now()}`;
      const name = (formData.get("name") as string) || "New Demo Capture";
      const tier = (formData.get("tier") as "standard" | "enhanced" | "premium") || "standard";

      const newCapture: VantageCamCapture = {
        capture_id: newId,
        name,
        tier,
        status: "processing",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        progress_percent: 0,
        current_stage: "probe",
      };

      // Add to demo captures
      DEMO_CAPTURES.push(newCapture);

      resolve(newCapture);
    }, 500);
  });
}

/**
 * Mock API: delete capture
 */
export async function mockDeleteCapture(captureId: string): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const idx = DEMO_CAPTURES.findIndex((c) => c.capture_id === captureId);
      if (idx >= 0) {
        DEMO_CAPTURES.splice(idx, 1);
      }
      resolve();
    }, 200);
  });
}
