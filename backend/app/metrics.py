"""
In-memory metrics for people counting.

Two distinct counters are maintained:
  - current_count: unique tracking IDs visible in the latest processed frame.
  - cumulative_count: total unique tracking IDs seen since session start (or reset).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Set


@dataclass
class PeopleMetrics:
    """
    Thread-safe store for live and cumulative headcount metrics.

    ByteTrack assigns persistent IDs across frames; we use those IDs as the
    unit of counting rather than raw bounding boxes.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _seen_ids: Set[int] = field(default_factory=set, repr=False)
    current_count: int = 0
    cumulative_count: int = 0
    fps: float = 0.0
    status: str = "idle"
    camera_index: int = 0
    is_running: bool = False

    def update_frame_ids(self, active_ids: Set[int]) -> None:
        """
        Update metrics after a tracked frame is processed.

        Args:
            active_ids: Set of ByteTrack IDs present in the current frame.
        """
        with self._lock:
            self.current_count = len(active_ids)
            self._seen_ids.update(active_ids)
            self.cumulative_count = len(self._seen_ids)

    def set_fps(self, fps: float) -> None:
        """Record smoothed processing FPS for dashboard display."""
        with self._lock:
            self.fps = round(fps, 1)

    def set_status(self, status: str) -> None:
        """Update human-readable pipeline status (e.g. running, paused, error)."""
        with self._lock:
            self.status = status

    def set_camera_index(self, index: int) -> None:
        with self._lock:
            self.camera_index = index

    def set_running(self, running: bool) -> None:
        with self._lock:
            self.is_running = running

    def reset_cumulative(self) -> None:
        """Clear historical unique-ID set; current frame count is unchanged."""
        with self._lock:
            self._seen_ids.clear()
            self.cumulative_count = 0

    def snapshot(self) -> dict:
        """Return a JSON-serializable metrics dict for WebSocket clients."""
        with self._lock:
            return {
                "current_count": self.current_count,
                "cumulative_count": self.cumulative_count,
                "fps": self.fps,
                "status": self.status,
                "camera_index": self.camera_index,
                "is_running": self.is_running,
            }
