"""
Deprecated camera helper.

This module previously contained server-side code that opened a local
webcam via OpenCV. The server no longer accesses hardware devices —
capture happens in the browser and frames are sent to the backend via
WebSocket. Keeping a small deprecation stub here so imports don't break
unexpectedly; avoid using this module.
"""

raise RuntimeError("server-side camera access has been removed; capture frames from the browser instead")


def _backend_candidates() -> List[Optional[int]]:
    """
    Build an ordered list of OpenCV capture backends to try.

    Windows: prefer DirectShow, then fall back to default.
    Other OS: use default backend only.
    """
    if platform.system() == "Windows":
        return [cv2.CAP_DSHOW, None]
    return [None]


def open_camera(preferred_index: int = 0) -> Tuple[cv2.VideoCapture, int]:
    """
    Attempt to open a webcam across indices and backends.

    Tries the preferred index first, then remaining indices in CAMERA_INDICES.
    Raises RuntimeError if no device opens successfully.

    Returns:
        Tuple of (VideoCapture handle, resolved camera index).
    """
    indices = [preferred_index] + [i for i in CAMERA_INDICES if i != preferred_index]
    errors: List[str] = []

    for index in indices:
        for backend in _backend_candidates():
            backend_name = "CAP_DSHOW" if backend == cv2.CAP_DSHOW else "default"
            try:
                cap = (
                    cv2.VideoCapture(index, backend)
                    if backend is not None
                    else cv2.VideoCapture(index)
                )
                if cap.isOpened():
                    # Warm-up read — some drivers need one frame before streaming.
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        logger.info(
                            "Camera opened: index=%s backend=%s resolution=%sx%s",
                            index,
                            backend_name,
                            frame.shape[1],
                            frame.shape[0],
                        )
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        return cap, index
                    cap.release()
                    errors.append(f"index={index} backend={backend_name}: opened but no frame")
                else:
                    if cap is not None:
                        cap.release()
                    errors.append(f"index={index} backend={backend_name}: not opened")
            except Exception as exc:
                errors.append(f"index={index} backend={backend_name}: {exc}")

    detail = "; ".join(errors)
    raise RuntimeError(f"Failed to open any camera. Attempts: {detail}")


class CameraStream:
    """
    Thin wrapper around cv2.VideoCapture for grab/release lifecycle.

    Frames are grabbed with read(); the tracker service owns processing.
    """

    def __init__(self, preferred_index: int = 0) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._index: int = preferred_index

    @property
    def index(self) -> int:
        return self._index

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def start(self, preferred_index: Optional[int] = None) -> int:
        """
        Open the camera. Re-opens if already active with a new index.

        Returns:
            Resolved camera index.
        """
        self.stop()
        idx = preferred_index if preferred_index is not None else self._index
        self._cap, self._index = open_camera(idx)
        return self._index

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Grab the next BGR frame from the webcam.

        Returns:
            (success, frame) — frame is None when capture fails.
        """
        if not self.is_open or self._cap is None:
            return False, None
        return self._cap.read()

    def stop(self) -> None:
        """
        Release camera hardware so other applications can use the device.

        Always call this when pausing or shutting down the processing loop.
        """
        if self._cap is not None:
            try:
                self._cap.release()
                logger.info("Camera released (index=%s)", self._index)
            except Exception as exc:
                logger.warning("Error releasing camera: %s", exc)
            finally:
                self._cap = None
