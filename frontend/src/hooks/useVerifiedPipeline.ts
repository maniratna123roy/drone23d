import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE_URL, verifiedPipelineApi } from "@/lib/api";
import { initialPipelineState, VerifiedPipelineSession } from "@/lib/verifiedPipelineSession";

function websocketUrl(): string {
  const configured = import.meta.env["VITE_WS_URL"] as string | undefined;
  if (configured) return configured;
  const url = new URL(API_BASE_URL || window.location.origin, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/scene";
  url.search = "";
  return url.toString();
}

/** Polling is authoritative and resumes after reload; WS only requests an earlier check. */
export function useVerifiedPipeline() {
  const [state, setState] = useState(initialPipelineState);
  const [connected, setConnected] = useState(false);
  const sessionRef = useRef<VerifiedPipelineSession | null>(null);
  useEffect(() => {
    const session = new VerifiedPipelineSession(verifiedPipelineApi, setState);
    sessionRef.current = session;
    session.start();
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnect: ReturnType<typeof setTimeout> | null = null;
    function connect() {
      if (stopped) return;
      try {
        socket = new WebSocket(websocketUrl());
        socket.onopen = () => {
          if (!stopped) setConnected(true);
        };
        socket.onmessage = (event) => {
          try {
            const diff: unknown = JSON.parse(String(event.data));
            if (
              typeof diff === "object" &&
              diff !== null &&
              "source" in diff &&
              (diff.source === "verified_video_pipeline" ||
                diff.source === "align_structures" ||
                diff.source === "publish_external_splat" ||
                diff.source === "scene_diff")
            )
              void session.refresh(true);
          } catch {
            /* Ignore unrelated/malformed notifications; polling still verifies the manifest. */
          }
        };
        socket.onerror = () => socket?.close();
        socket.onclose = () => {
          if (stopped) return;
          setConnected(false);
          reconnect = setTimeout(connect, 5000);
        };
      } catch {
        if (!stopped) reconnect = setTimeout(connect, 5000);
      }
    }
    connect();
    return () => {
      stopped = true;
      if (reconnect) clearTimeout(reconnect);
      if (socket) {
        socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null;
        socket.close();
      }
      session.stop();
      if (sessionRef.current === session) sessionRef.current = null;
    };
  }, []);
  const refresh = useCallback((): Promise<void> => {
    return sessionRef.current?.refresh(true) ?? Promise.resolve();
  }, []);
  const upload = useCallback((file: File) => {
    void sessionRef.current?.upload(file);
  }, []);
  return { ...state, connected, refresh, upload };
}
