/** Real-time metrics payload from the backend tracker service. */
export interface Metrics {
  current_count: number;
  cumulative_count: number;
  fps: number;
  status: string;
  camera_index: number;
  is_running: boolean;
}

/** WebSocket message shapes pushed by the FastAPI server. */
export interface FrameMessage {
  type: "frame";
  image: string;
  metrics: Metrics;
}

export interface HeartbeatMessage {
  type: "heartbeat" | "pong";
  metrics: Metrics;
}

export type StreamMessage = FrameMessage | HeartbeatMessage;
