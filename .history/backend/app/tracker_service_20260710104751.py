"""
YOLO + ByteTrack processing service for frames submitted by clients.

This service no longer opens a server-side webcam. Instead, callers
provide individual BGR frames (from browser-captured JPEGs) to
``process_frame``. The model is kept loaded across calls so that
``persist=True`` tracking / ByteTrack state remains active across
consecutive frames from the same client session.

The high-level per-frame steps are:
    1. Run ``model.track`` with ``persist=True`` for stable track IDs.
    2. Filter detections to class "person" (COCO id 0).
    3. Annotate boxes and tracking IDs on the frame.
    4. Update current/cumulative metrics from active track IDs.
    5. Encode the annotated frame as JPEG (base64) for transport.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Callable, Optional, Set

import cv2
import numpy as np
from ultralytics import YOLO
from .config import (
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    JPEG_QUALITY,
    MODEL_CANDIDATES,
    PERSON_CLASS_ID,
    TARGET_FPS,
    TRACKER_CONFIG,
)
from .metrics import PeopleMetrics

logger = logging.getLogger(__name__)


def _load_yolo_model() -> YOLO:
    """Load the first available lightweight YOLO weights file."""
    last_error: Optional[Exception] = None
    for name in MODEL_CANDIDATES:
        try:
            model = YOLO(name)
            logger.info("Loaded YOLO model: %s", name)
            return model
        except Exception as exc:
            last_error = exc
            logger.warning("Could not load %s: %s", name, exc)
    raise RuntimeError(f"No YOLO model could be loaded: {last_error}")


def _extract_person_track_ids(results) -> Set[int]:
    """
    Collect ByteTrack IDs for person detections in the latest result.

    Ultralytics stores per-detection class ids and track ids on boxes when
    tracking is enabled.
    """
    active_ids: Set[int] = set()
    if not results or results[0].boxes is None:
        return active_ids

    boxes = results[0].boxes
    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        if cls_id != PERSON_CLASS_ID:
            continue
        if boxes.id is None:
            continue
        track_id = int(boxes.id[i].item())
        active_ids.add(track_id)
    return active_ids


class TrackerService:
    """
    Stateless service that processes frames supplied by remote clients.

    The service keeps a YOLO model instance in memory so that tracking
    state is preserved across frames when called with ``persist=True``.
    """

    def __init__(self, metrics: PeopleMetrics) -> None:
        self.metrics = metrics
        self._model: Optional[YOLO] = None
        # Optional callback invoked after processing a frame. Kept for
        # backwards compatibility with older code paths; not required.
        self._frame_callback: Optional[Callable[[str, dict], None]] = None
        self._last_time: Optional[float] = None

    def set_frame_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Register a function invoked each processed frame (jpeg_b64, metrics)."""
        self._frame_callback = callback

    def _ensure_model(self) -> YOLO:
        if self._model is None:
            self._model = _load_yolo_model()
        return self._model

    def start(self) -> None:
        """Mark the service as running (frontend clients may start sending frames)."""
        self.metrics.set_running(True)
        self.metrics.set_status("running")

    def pause(self) -> None:
        """Mark the service as paused. Tracking state in the model is preserved."""
        self.metrics.set_running(False)
        self.metrics.set_status("paused")

    def reset_cumulative(self) -> None:
        self.metrics.reset_cumulative()

    def change_camera(self, camera_index: int) -> None:
        """No-op for server-side camera; keep metric for UI parity."""
        self.metrics.set_camera_index(camera_index)

    def process_frame(self, frame: np.ndarray) -> tuple[str, dict]:
        """
        Process a single BGR frame and return (jpeg_b64, metrics_snapshot).

        This function is synchronous and expected to be called from an
        async WebSocket handler — callers should run it in a threadpool
        if non-blocking behavior is required.
        """
        model = self._ensure_model()
        loop_start = time.perf_counter()

        try:
            results = model.track(
                frame,
                persist=True,
                tracker=TRACKER_CONFIG,
                classes=[PERSON_CLASS_ID],
                conf=CONFIDENCE_THRESHOLD,
                iou=IOU_THRESHOLD,
                verbose=False,
            )

            annotated = results[0].plot() if results else frame

            active_ids = _extract_person_track_ids(results)
            self.metrics.update_frame_ids(active_ids)

            ok, buffer = cv2.imencode(
                ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            jpeg_b64 = ""
            if ok:
                jpeg_b64 = base64.b64encode(buffer.tobytes()).decode("ascii")
                if self._frame_callback:
                    self._frame_callback(jpeg_b64, self.metrics.snapshot())

        except Exception as exc:
            logger.exception("Tracking frame error")
            self.metrics.set_status(f"tracking error: {exc}")

        # Update a smoothed FPS estimate.
        now = time.perf_counter()
        if self._last_time is not None:
            instant_fps = 1.0 / (now - self._last_time) if (now - self._last_time) > 0 else 0.0
            prev = self.metrics.snapshot().get("fps", 0) or 0
            fps_smooth = 0.9 * prev + 0.1 * instant_fps if prev else instant_fps
            self.metrics.set_fps(fps_smooth)
        self._last_time = now

        return jpeg_b64, self.metrics.snapshot()
