import type { Metrics } from "../types";

interface StatCardsProps {
  metrics: Metrics;
  connected: boolean;
}

/**
 * High-visibility analytics cards for occupancy, traffic, and system health.
 */
export function StatCards({ metrics, connected }: StatCardsProps) {
  const fpsLabel = metrics.fps > 0 ? `${metrics.fps} FPS` : "— FPS";
  const health = connected
    ? metrics.is_running
      ? "Streaming"
      : metrics.status
    : "Disconnected";

  return (
    <section className="stat-grid" aria-label="Analytics overview">
      <article className="stat-card stat-card--primary">
        <div className="stat-card__label">Live Headcount</div>
        <div className="stat-card__value">{metrics.current_count}</div>
        <div className="stat-card__hint">People in frame right now</div>
      </article>

      <article className="stat-card stat-card--accent">
        <div className="stat-card__label">Total Unique Visitors</div>
        <div className="stat-card__value">{metrics.cumulative_count}</div>
        <div className="stat-card__hint">Since session start</div>
      </article>

      <article className="stat-card stat-card--system">
        <div className="stat-card__label">System FPS / Status</div>
        <div className="stat-card__value stat-card__value--sm">{fpsLabel}</div>
        <div className="stat-card__hint">
          <span className={`health-badge ${connected && metrics.is_running ? "ok" : "warn"}`}>
            {health}
          </span>
          {" · "}Camera {metrics.camera_index}
        </div>
      </article>
    </section>
  );
}
