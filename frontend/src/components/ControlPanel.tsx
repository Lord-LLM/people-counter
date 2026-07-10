interface ControlPanelProps {
  cameraIndex: number;
  isRunning: boolean;
  loading: boolean;
  error: string | null;
  onCameraChange: (index: number) => void;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
}

/**
 * Interactive controls: start/pause stream, reset cumulative counter,
 * and select webcam index (0, 1, 2).
 */
export function ControlPanel({
  cameraIndex,
  isRunning,
  loading,
  error,
  onCameraChange,
  onStart,
  onPause,
  onReset,
}: ControlPanelProps) {
  return (
    <section className="control-panel" aria-label="Stream controls">
      <h2 className="control-panel__title">Controls</h2>

      <div className="control-row">
        <label htmlFor="camera-select" className="control-label">
          Camera Index
        </label>
        <select
          id="camera-select"
          className="control-select"
          value={cameraIndex}
          onChange={(e) => onCameraChange(Number(e.target.value))}
          disabled={loading}
        >
          <option value={0}>Camera 0</option>
          <option value={1}>Camera 1</option>
          <option value={2}>Camera 2</option>
        </select>
      </div>

      <div className="control-actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={onStart}
          disabled={loading || isRunning}
        >
          {loading && !isRunning ? "Starting…" : "Start Stream"}
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={onPause}
          disabled={loading || !isRunning}
        >
          Pause
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={onReset}
          disabled={loading}
        >
          Reset Counter
        </button>
      </div>

      {error && (
        <p className="control-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
