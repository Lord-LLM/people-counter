import { useCallback, useEffect, useRef, useState } from "react";
import type { Metrics, StreamMessage } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

function deriveWsUrl(): string {
  // If VITE_API_URL is provided (e.g. https://api.example.com), derive
  // the ws:// or wss:// URL from the page protocol and the host portion.
  if (API_BASE) {
    try {
      const u = new URL(API_BASE);
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      return `${scheme}://${u.host}/ws/stream`;
    } catch {
      // Fall back to assuming it's already a host:port string.
    }
  }
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/stream`;
}

const WS_URL = deriveWsUrl();

const DEFAULT_METRICS: Metrics = {
  current_count: 0,
  cumulative_count: 0,
  fps: 0,
  status: "disconnected",
  camera_index: 0,
  is_running: false,
};

/**
 * Maintains a resilient WebSocket connection to the backend stream.
 *
 * Receives annotated JPEG frames (base64) and metrics each tick so the
 * dashboard can update without polling HTTP.
 */
export function useStreamSocket() {
  const [imageSrc, setImageSrc] = useState<string>("");
  const [metrics, setMetrics] = useState<Metrics>(DEFAULT_METRICS);
  const [connected, setConnected] = useState(false);
  const [waking, setWaking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttempts = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setMetrics((m) => ({ ...m, status: m.status === "disconnected" ? "connected" : m.status }));
      reconnectAttempts.current = 0;
      setWaking(false);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as StreamMessage;
        if ("metrics" in data) {
          setMetrics(data.metrics);
        }
        if (data.type === "frame" && data.image) {
          setImageSrc(`data:image/jpeg;base64,${data.image}`);
        }
      } catch {
        // Ignore malformed payloads.
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectAttempts.current += 1;
      const attempts = reconnectAttempts.current;
      // If several reconnect attempts occur, surface a "waking" state
      // to the UI so the user knows the backend may be spinning up.
      if (attempts >= 2) setWaking(true);
      setMetrics((m) => ({ ...m, status: "disconnected" }));
      const backoff = Math.min(2000 * attempts, 10000);
      reconnectTimer.current = setTimeout(connect, backoff);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendFrame = useCallback((data: ArrayBuffer | Blob) => {
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
        return true;
      }
    } catch {
      // ignore
    }
    return false;
  }, []);

  return { imageSrc, metrics, connected, waking, sendFrame };
}

async function postJson(path: string, body?: object) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

/** REST helpers for start / pause / reset / camera selection. */
export function useControls() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setLoading(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const start = (cameraIndex: number) =>
    run(() => postJson("/api/start", { camera_index: cameraIndex }));

  const pause = () => run(() => postJson("/api/pause"));

  const reset = () => run(() => postJson("/api/reset"));

  const setCamera = (cameraIndex: number) =>
    run(() => postJson("/api/camera", { camera_index: cameraIndex }));

  return { start, pause, reset, setCamera, loading, error };
}
