"""
FastAPI entry point — HTTP control API + WebSocket live stream.

REST endpoints start/pause/reset the tracker and switch cameras.
WebSocket /ws/stream pushes annotated JPEG frames and metrics each tick.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Set

import os
import base64
import numpy as np
import cv2

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .metrics import PeopleMetrics
from .tracker_service import TrackerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

metrics = PeopleMetrics()
tracker = TrackerService(metrics)

# Connected WebSocket clients and latest broadcast payload.
_clients: Set[WebSocket] = set()
_latest_payload: dict = {"type": "frame", "image": "", "metrics": metrics.snapshot()}
_broadcast_lock = asyncio.Lock()
_main_loop: asyncio.AbstractEventLoop | None = None


def _on_frame(jpeg_b64: str, snapshot: dict) -> None:
    """Compatibility hook — unused in browser-capture mode."""
    global _latest_payload
    _latest_payload = {"type": "frame", "image": jpeg_b64, "metrics": snapshot}
    if _main_loop and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast_latest(), _main_loop)


async def _broadcast_latest() -> None:
    """Push the most recent frame + metrics to every connected client."""
    if not _clients:
        return
    async with _broadcast_lock:
        dead: List[WebSocket] = []
        for ws in list(_clients):
            try:
                await ws.send_json(_latest_payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan: record event loop and preload model weights.

    Preloading the model during startup reduces first-request latency
    (weights are also downloaded at Docker build time when possible).
    """
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    # Ensure model is loaded at startup to avoid blocking the first WS frame.
    try:
        tracker._ensure_model()
        logger.info("YOLO model preloaded at startup")
    except Exception as exc:
        logger.exception("Model preload failed: %s", exc)
    tracker.set_frame_callback(_on_frame)
    logger.info("People Counter API ready")
    yield
    tracker.pause()
    logger.info("Shutdown complete — tracker paused")


app = FastAPI(
    title="People Counter API",
    description="Real-time YOLO + ByteTrack people counting",
    version="1.0.0",
    lifespan=lifespan,
)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN")
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if FRONTEND_ORIGIN:
    ALLOWED_ORIGINS.append(FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRequest(BaseModel):
    camera_index: int = Field(default=0, ge=0, le=2)


class CameraRequest(BaseModel):
    camera_index: int = Field(ge=0, le=2)


@app.get("/health")
async def health():
    return {"status": "ok", "metrics": metrics.snapshot()}


@app.get("/api/metrics")
async def get_metrics():
    return metrics.snapshot()


@app.post("/api/start")
async def start_stream(body: StartRequest):
    """
    Begin a browser-driven tracking session.

    `camera_index` is still accepted in the request body for frontend UI
    compatibility, but the server no longer opens a physical camera.
    """
    tracker.start()
    return {"message": "stream started", "metrics": metrics.snapshot()}


@app.post("/api/pause")
async def pause_stream():
    """Pause tracking and release the webcam."""
    tracker.pause()
    return {"message": "stream paused", "metrics": metrics.snapshot()}


@app.post("/api/reset")
async def reset_counter():
    """Reset cumulative unique visitor count to zero."""
    tracker.reset_cumulative()
    return {"message": "cumulative counter reset", "metrics": metrics.snapshot()}


@app.post("/api/camera")
async def set_camera(body: CameraRequest):
    """Switch to a different camera index (0, 1, or 2)."""
    tracker.change_camera(body.camera_index)
    return {
        "message": f"camera set to index {body.camera_index}",
        "metrics": metrics.snapshot(),
    }


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint that accepts frames from the browser and returns
    annotated frames + metrics. Accepts either raw binary JPEG frames or
    JSON messages containing a base64-encoded image.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    # Immediately send a metrics snapshot so UI can show current state.
    await websocket.send_json({"type": "hello", "metrics": metrics.snapshot()})

    try:
        while True:
            # Receive either binary JPEG frames or JSON control messages.
            message = await websocket.receive()

            # Binary frame (raw JPEG bytes)
            if message.get("type") == "bytes":
                data = message.get("bytes")
                try:
                    arr = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is None:
                        raise ValueError("could not decode image")

                    # Offload CPU-heavy processing to threadpool to avoid
                    # blocking the event loop.
                    loop = asyncio.get_running_loop()
                    jpeg_b64, snap = await loop.run_in_executor(None, tracker.process_frame, frame)
                    await websocket.send_json({"type": "frame", "image": jpeg_b64, "metrics": snap})
                except WebSocketDisconnect:
                    logger.info("WebSocketDisconnect during binary processing")
                    return
                except RuntimeError as exc:
                    # Starlette may raise a RuntimeError when receive() is
                    # called after a disconnect; treat this as a clean exit.
                    if "Cannot call \"receive\" once a disconnect message has been received" in str(exc):
                        logger.info("WebSocket closed (receive after disconnect)")
                        return
                    logger.exception("Failed to process binary frame: %s", exc)
                    try:
                        await websocket.send_json({"type": "error", "message": str(exc)})
                    except Exception:
                        return
                except Exception as exc:
                    logger.exception("Failed to process binary frame: %s", exc)
                    try:
                        await websocket.send_json({"type": "error", "message": str(exc)})
                    except Exception:
                        return

            # Textual messages: JSON control or base64 images
            elif message.get("type") == "text":
                text = message.get("text")
                try:
                    msg = None
                    try:
                        msg = websocket.json_loads(text) if hasattr(websocket, "json_loads") else __import__("json").loads(text)
                    except Exception:
                        # Not JSON, ignore
                        msg = None

                    if isinstance(msg, dict) and msg.get("action") == "ping":
                        await websocket.send_json({"type": "pong", "metrics": metrics.snapshot()})

                    # Accept base64-encoded payload { image: "data:...base64..." }
                    elif isinstance(msg, dict) and msg.get("image"):
                        payload = msg.get("image")
                        # support data URLs or raw base64
                        if payload.startswith("data:"):
                            payload = payload.split(",", 1)[1]
                        data = base64.b64decode(payload)
                        arr = np.frombuffer(data, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        loop = asyncio.get_running_loop()
                        jpeg_b64, snap = await loop.run_in_executor(None, tracker.process_frame, frame)
                        await websocket.send_json({"type": "frame", "image": jpeg_b64, "metrics": snap})

                except WebSocketDisconnect:
                    logger.info("WebSocketDisconnect during text processing")
                    return
                except RuntimeError as exc:
                    if "Cannot call \"receive\" once a disconnect message has been received" in str(exc):
                        logger.info("WebSocket closed (receive after disconnect)")
                        return
                    logger.exception("Error handling text websocket message: %s", exc)
                    try:
                        await websocket.send_json({"type": "error", "message": str(exc)})
                    except Exception:
                        return
                except Exception as exc:
                    logger.exception("Error handling text websocket message: %s", exc)
                    try:
                        await websocket.send_json({"type": "error", "message": str(exc)})
                    except Exception:
                        return

            else:
                # Unknown message type — ignore silently.
                continue

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        return
    except RuntimeError as exc:
        if "Cannot call \"receive\" once a disconnect message has been received" in str(exc):
            logger.info("WebSocket closed (receive after disconnect)")
            return
        logger.warning("WebSocket error: %s", exc)
        return
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
        return
