import { useEffect, useRef, useCallback } from "react";
import { useVantageCamStore } from "@/store/vantagecamStore";
import type { VantageCamEvent, VantageCamQualityReport } from "@/types/vantagecam";

/**
 * useVantageCamWebSocket
 *
 * Connects to backend WebSocket at /ws/vantagecam/{capture_id} for real-time progress streaming.
 *
 * Analogy: Like a live scoreboard showing each stage of the pipeline as it runs:
 * each stage starts, shows progress (25%, 50%, 75%), then completes. When the
 * pipeline finishes, the final quality report is sent.
 *
 * Message format (from backend):
 * {
 *   type: "stage_start" | "stage_progress" | "stage_complete" | "stage_error" | ...
 *   capture_id: "uuid",
 *   stage_index: 0-9,
 *   stage_name: "probe" | "frames" | ... | "export",
 *   progress: 0-100,
 *   timestamp: milliseconds since pipeline start,
 *   duration_ms: stage duration if complete,
 *   metadata: { artifacts, quality_metrics, ... }
 * }
 */

interface UseVantageCamWebSocketOptions {
  captureId?: string | null;
  onQualityReport?: (report: VantageCamQualityReport) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
}

export function useVantageCamWebSocket({
  captureId = null,
  onQualityReport,
  autoReconnect = true,
  maxReconnectAttempts = 5,
}: UseVantageCamWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const { addEvent, setConnected, setError, setQualityReport } =
    useVantageCamStore();

  const connect = useCallback(
    (id: string) => {
      // Don't reconnect if we already have an active connection
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        console.log(`[VantageCam WS] Already connected to capture ${id}`);
        return;
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/vantagecam/${id}`;

      console.log(`[VantageCam WS] Connecting to ${wsUrl}`);

      try {
        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onopen = () => {
          console.log(`[VantageCam WS] Connected to capture ${id}`);
          reconnectCountRef.current = 0;
          setConnected(true);
          setError(null);
        };

        wsRef.current.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);

            // Validate message structure
            if (!message.type || !message.capture_id) {
              console.warn(
                "[VantageCam WS] Invalid message structure:",
                message
              );
              return;
            }

            const typedEvent = message as VantageCamEvent;
            console.log(
              `[VantageCam WS] Received ${typedEvent.type}: ${typedEvent.stage_name || ""}`,
              typedEvent
            );

            // Add event to store
            addEvent(typedEvent);

            // Handle pipeline completion
            if (typedEvent.type === "pipeline_complete") {
              // Extract quality report from metadata if present
              const report: VantageCamQualityReport = {
                capture_id: typedEvent.capture_id,
                verdict: "PASS",
                total_duration_ms: typedEvent.timestamp || 0,
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
                artifacts: typedEvent.metadata?.artifacts?.map((name: string) => ({
                  name,
                  size_bytes: 0,
                  created_at: new Date().toISOString(),
                  url: `/api/vantagecam/captures/${typedEvent.capture_id}/artifacts/${name}`,
                })) || [],
                metrics: typedEvent.metadata?.quality_metrics || {},
              };

              setQualityReport(report);
              onQualityReport?.(report);
            }

            // Handle pipeline failure
            if (typedEvent.type === "pipeline_failed") {
              const report: VantageCamQualityReport = {
                capture_id: typedEvent.capture_id,
                verdict: "FAIL",
                total_duration_ms: typedEvent.timestamp || 0,
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
                error_logs: typedEvent.error_message,
              };

              setQualityReport(report);
              setError(`Pipeline failed: ${typedEvent.error_message}`);
              onQualityReport?.(report);
            }
          } catch (error) {
            console.error("[VantageCam WS] Failed to parse message:", error);
            setError("Failed to parse WebSocket message");
          }
        };

        wsRef.current.onerror = (event) => {
          console.error("[VantageCam WS] WebSocket error:", event);
          setError("WebSocket connection error");
        };

        wsRef.current.onclose = () => {
          console.log(`[VantageCam WS] Disconnected from capture ${id}`);
          setConnected(false);

          // Attempt reconnection
          if (autoReconnect && reconnectCountRef.current < maxReconnectAttempts) {
            reconnectCountRef.current++;
            const backoffMs = Math.min(1000 * 2 ** reconnectCountRef.current, 30000);
            console.log(
              `[VantageCam WS] Reconnecting in ${backoffMs}ms... (attempt ${reconnectCountRef.current}/${maxReconnectAttempts})`
            );

            reconnectTimeoutRef.current = setTimeout(() => {
              connect(id);
            }, backoffMs);
          } else if (reconnectCountRef.current >= maxReconnectAttempts) {
            console.error("[VantageCam WS] Max reconnection attempts reached");
            setError("Connection lost. Max reconnection attempts exceeded.");
          }
        };
      } catch (error) {
        console.error("[VantageCam WS] Failed to create WebSocket:", error);
        setError("Failed to create WebSocket connection");
      }
    },
    [addEvent, setConnected, setError, setQualityReport, onQualityReport, autoReconnect, maxReconnectAttempts]
  );

  // Connect when captureId changes
  useEffect(() => {
    if (!captureId) {
      // Disconnect if no capture ID
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      setConnected(false);
      return;
    }

    connect(captureId);

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [captureId, connect, setConnected]);

  // Manual disconnect function
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    setConnected(false);
  }, [setConnected]);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    disconnect,
  };
}
