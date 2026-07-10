interface VideoStreamProps {
  imageSrc: string;
  status: string;
  isRunning: boolean;
}

/**
 * Center-stage live feed showing YOLO-annotated frames from the backend.
 * Frames arrive as base64 JPEG over WebSocket and are rendered via <img>.
 */
export function VideoStream({ imageSrc, status, isRunning }: VideoStreamProps) {
  return (
    <section className="video-stage" aria-label="Live annotated video stream">
      <div className="video-frame">
        {imageSrc ? (
          <img src={imageSrc} alt="Live people tracking feed" className="video-image" />
        ) : (
          <div className="video-placeholder">
            <div className="placeholder-icon" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <p>Press <strong>Start Stream</strong> to begin live tracking</p>
            <span className="placeholder-hint">YOLO + ByteTrack · Person class only</span>
          </div>
        )}
        <div className="video-overlay">
          <span className={`status-pill ${isRunning ? "live" : "idle"}`}>
            <span className="status-dot" />
            {isRunning ? "LIVE" : status.toUpperCase()}
          </span>
        </div>
      </div>
    </section>
  );
}
