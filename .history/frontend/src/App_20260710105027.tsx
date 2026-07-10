import { useEffect, useRef, useState } from "react";
import { ControlPanel } from "./components/ControlPanel";
import { StatCards } from "./components/StatCards";
import { VideoStream } from "./components/VideoStream";
import { useControls, useStreamSocket } from "./hooks/useWebSocket";

/**
 * Root dashboard: WebSocket live feed + REST controls.
 *
 * Data flow:
 *   Webcam → YOLO/ByteTrack (backend) → WebSocket JPEG + metrics → React UI
 */
export default function App() {
  const { imageSrc, metrics, connected } = useStreamSocket();
  const { start, pause, reset, setCamera, loading, error } = useControls();
  const [cameraIndex, setCameraIndex] = useState(0);
  const { sendFrame, waking } = useStreamSocket() as any;

  // Refs for local capture
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mediaRef = useRef<MediaStream | null>(null);
  const captureTimer = useRef<number | null>(null);
  const deviceIds = useRef<string[]>([]);

  useEffect(() => {
    // Enumerate video input devices so cameraIndex maps to a deviceId.
    navigator.mediaDevices
      .enumerateDevices()
      .then((devices) => {
        deviceIds.current = devices.filter((d) => d.kind === "videoinput").map((d) => d.deviceId);
      })
      .catch(() => {
        deviceIds.current = [];
      });
    return () => {
      // ensure capture is stopped on unmount
      stopCapture();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCameraChange = async (index: number) => {
    setCameraIndex(index);
    if (metrics.is_running) {
      await setCamera(index);
    }
  };

  function stopCapture() {
    if (captureTimer.current) {
      window.clearInterval(captureTimer.current);
      captureTimer.current = null;
    }
    if (mediaRef.current) {
      mediaRef.current.getTracks().forEach((t) => t.stop());
      mediaRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  const startCapture = async () => {
    // Start local webcam capture and send frames at ~120ms intervals.
    const deviceId = deviceIds.current[cameraIndex];
    const constraints: MediaStreamConstraints = {
      video: deviceId ? { deviceId: { exact: deviceId } } : { width: { ideal: 1280 } },
      audio: false,
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    mediaRef.current = stream;
    if (!videoRef.current) {
      videoRef.current = document.createElement("video");
      videoRef.current.setAttribute("playsinline", "true");
      videoRef.current.muted = true;
    }
    videoRef.current.srcObject = stream;
    await videoRef.current.play();

    if (!canvasRef.current) {
      canvasRef.current = document.createElement("canvas");
    }

    const sendInterval = 120; // ms between frames
    captureTimer.current = window.setInterval(() => {
      try {
        const video = videoRef.current!;
        const canvas = canvasRef.current!;
        const scale = Math.min(1, 640 / video.videoWidth || 1);
        const w = Math.max(1, Math.floor((video.videoWidth || 640) * scale));
        const h = Math.max(1, Math.floor((video.videoHeight || 480) * scale));
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, w, h);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.6);
        // Send as binary to backend (strip data URL prefix)
        const base64 = dataUrl.split(",")[1];
        const binary = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
        sendFrame(binary.buffer);
      } catch (e) {
        // ignore transient capture errors
      }
    }, sendInterval);
  };

  const handleStart = async () => {
    await start(cameraIndex);
    try {
      await startCapture();
    } catch (e) {
      console.error("Failed to start capture:", e);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="brand-icon" aria-hidden>
            <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
            </svg>
          </span>
          <div>
            <h1 className="app-header__title">People Counter</h1>
            <p className="app-header__subtitle">Real-time occupancy · YOLO11 + ByteTrack</p>
          </div>
        </div>
        <div className={`connection-badge ${connected ? "on" : "off"}`}>
          {connected ? "WS Connected" : "WS Reconnecting…"}
        </div>
      </header>

      <main className="app-main">
        <StatCards metrics={metrics} connected={connected} />

        <div className="main-stage">
          <VideoStream
            imageSrc={imageSrc}
            status={metrics.status}
            isRunning={metrics.is_running}
          />
          <aside className="sidebar">
            <ControlPanel
              cameraIndex={cameraIndex}
              isRunning={metrics.is_running}
              loading={loading}
              error={error}
              onCameraChange={handleCameraChange}
              onStart={handleStart}
              onPause={pause}
              onReset={reset}
            />

            <div className="info-card">
              <h3>How it works</h3>
              <ol>
                <li>Webcam frames are captured on the backend.</li>
                <li>YOLO detects persons (class 0) only.</li>
                <li>ByteTrack assigns persistent IDs across frames.</li>
                <li>Annotated video + metrics stream via WebSocket.</li>
              </ol>
            </div>
          </aside>
        </div>
      </main>

      <footer className="app-footer">
        Fixed-room people counting · Ultralytics YOLO · ByteTrack
      </footer>
    </div>
  );
}
