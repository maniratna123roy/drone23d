import { useEffect, useRef, useCallback } from "react";
import { useSpatialStore } from "@/store/spatialStore";
import { API_BASE_URL } from "@/lib/api";

/**
 * useWebSocket
 *
 * Connects to backend WebSocket at /ws/scene for real-time updates.
 * Listens for scene_diff messages that contain updated object IDs.
 *
 * Analogy: Like a live chat where you receive updates when someone else
 * edits the scene. Multi-tab sync happens automatically.
 *
 * Message format (from backend):
 * {
 *   updated: [id1, id2, ...],  // object IDs that changed
 *   removed: [id3, ...],       // object IDs that were deleted
 *   version: N                 // scene version counter for consistency
 * }
 */

interface SceneDiff {
  updated?: string[];
  removed?: string[];
  version?: number;
}

export function useWebSocket(url: string = "ws://127.0.0.1:8000/ws/scene") {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const maxReconnectAttempts = 5;

  const {
    updateSceneVersion,
    setObjects,
    objects,
    setHighlightedObjectIds,
  } = useSpatialStore();

  const connect = useCallback(() => {
    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
        reconnectCountRef.current = 0;
      };

      wsRef.current.onmessage = async (event) => {
        try {
          const diff = JSON.parse(event.data);

          // Update scene version counter
          if (diff.version !== undefined) {
            updateSceneVersion();
          }

          // Handle updated or restored objects from edit or undo
          if (diff.updated && diff.updated.length > 0) {
            console.log(`[WebSocket] Received scene_diff for updated objects:`, diff.updated);
            // Re-fetch structures from backend to keep state 100% in sync
            try {
              const res = await fetch(`${API_BASE_URL}/api/objects/structures?_t=${Date.now()}`, { cache: "no-store" });
              if (res.ok) {
                const rawStructures = await res.json();
                const mapped = rawStructures.map((s: any) => {
                  const bbox = s.splat_bbox || {};
                  const minX = bbox.min_x ?? -10;
                  const maxX = bbox.max_x ?? 10;
                  const minY = bbox.min_y ?? -10;
                  const maxY = bbox.max_y ?? 10;
                  const minZ = bbox.min_z ?? 0;

                  return {
                    id: String(s.id),
                    label: `Building #${s.id} (${s.region || "Structure"})`,
                    layer: "buildings",
                    x: (minX + maxX) / 2.0,
                    z: (minY + maxY) / 2.0,
                    width: Math.max(1.0, maxX - minX),
                    depth: Math.max(1.0, maxY - minY),
                    height: Number(s.height_m || 20.0),
                    elevationM: Number(minZ || 0.0),
                    areaM2: Number(s.area_m2 || 150.0),
                    region: s.region || "CENTER",
                    footprint: s.footprint,
                    splatBbox: bbox,
                    originalHeightM: s.original_height_m,
                    version: s.version || 1,
                  };
                });
                setObjects(mapped);
              }
            } catch (err) {
              console.error("[WebSocket] Failed to reload structures after scene_diff:", err);
            }
          }

          // Handle removed objects
          if (diff.removed && diff.removed.length > 0) {
            const updatedObjects = objects.filter(
              (obj) => !diff.removed?.includes(obj.id)
            );
            setObjects(updatedObjects);
          }
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      wsRef.current.onerror = (event) => {
        console.error("WebSocket error:", event);
      };

      wsRef.current.onclose = () => {
        console.log("WebSocket disconnected");
        // Attempt reconnection
        if (reconnectCountRef.current < maxReconnectAttempts) {
          reconnectCountRef.current++;
          const backoffMs = Math.min(1000 * 2 ** reconnectCountRef.current, 30000);
          console.log(`Reconnecting in ${backoffMs}ms...`);
          setTimeout(() => {
            connect();
          }, backoffMs);
        } else {
          console.error("Max reconnection attempts reached");
        }
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
    }
  }, [url, updateSceneVersion, setObjects, objects, setHighlightedObjectIds]);

  // Connect on mount
  useEffect(() => {
    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  // Send message function
  const send = useCallback((data: unknown) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    send,
  };
}
