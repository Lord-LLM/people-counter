"""
Application configuration for the people-counting backend.

Centralizes model paths, camera defaults, and streaming parameters so the
rest of the pipeline can stay focused on capture, tracking, and delivery.
"""

from pathlib import Path

# Base directory for backend assets (models, tracker configs).
BASE_DIR = Path(__file__).resolve().parent.parent

# YOLO model: prefer yolo11n for speed; falls back to yolov8n if unavailable.
MODEL_CANDIDATES = ["yolo11n.pt", "yolov8n.pt"]

# COCO class index for "person" — we restrict detection to this class only.
PERSON_CLASS_ID = 0

# Local ByteTrack config (also compatible with Ultralytics built-in name).
TRACKER_CONFIG = str(BASE_DIR / "bytetrack.yaml")

# Camera indices tried when opening a webcam (user can also pick via API).
CAMERA_INDICES = [0, 1, 2]

# JPEG quality for frames sent over WebSocket (balance bandwidth vs clarity).
JPEG_QUALITY = 80

# Target loop rate; actual FPS depends on hardware and model inference time.
TARGET_FPS = 30

# Confidence threshold for person detections.
CONFIDENCE_THRESHOLD = 0.45

# IoU threshold for non-max suppression during tracking.
IOU_THRESHOLD = 0.5
