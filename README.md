# People Counter — Real-Time People Tracking Dashboard

Production-ready web application for **real-time people counting and tracking** using a fixed webcam. Built with **YOLO11/YOLOv8** (Ultralytics) and **ByteTrack** for persistent object IDs.

## Architecture

```
┌─────────────┐     WebSocket (JPEG + metrics)      ┌──────────────────┐
│   React UI  │ ◄────────────────────────────────── │  FastAPI Backend │
│  Dashboard  │     REST (/api/start, pause, …)     │  YOLO + ByteTrack│
└─────────────┘ ──────────────────────────────────► └────────┬─────────┘
                                                               │
                                                        ┌──────▼──────┐
                                                        │   Webcam    │
                                                        └─────────────┘
```

### Backend pipeline (per frame)

1. **Grab** — `cv2.VideoCapture.read()` pulls a BGR frame from the webcam.
2. **Detect + Track** — `model.track(persist=True, tracker="bytetrack.yaml", classes=[0])` runs YOLO on persons only; ByteTrack maintains IDs across frames.
3. **Count** — Active track IDs → **Live Headcount**; union of all IDs seen → **Total Unique Visitors**.
4. **Annotate** — `results[0].plot()` draws boxes and IDs on the frame.
5. **Serve** — Frame is JPEG-encoded to base64 and pushed over WebSocket with metrics.

### Metrics

| Metric | Description |
|--------|-------------|
| **Live Headcount** | Unique tracking IDs in the current frame |
| **Total Unique Visitors** | All unique IDs since session start (resettable) |
| **FPS / Status** | Smoothed processing rate and camera health |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Webcam (USB or built-in)
- Optional: NVIDIA GPU + CUDA for higher FPS

### 1. Backend

```bash
cd people-counter/backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

API: `http://localhost:8000`  
WebSocket: `ws://localhost:8000/ws/stream`

On first run, Ultralytics downloads `yolo11n.pt` (or falls back to `yolov8n.pt`).

### 2. Frontend

```bash
cd people-counter/frontend
npm install
npm run dev
```

Dashboard: `http://localhost:5173`

Vite proxies `/api` and `/ws` to the backend during development.

### 3. Use the dashboard

1. Open `http://localhost:5173`
2. Select camera index (0, 1, or 2) if needed
3. Click **Start Stream**
4. View live annotated video and analytics cards
5. **Pause** stops capture and releases the webcam
6. **Reset Counter** clears cumulative unique visitors

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + metrics snapshot |
| `GET` | `/api/metrics` | Current metrics JSON |
| `POST` | `/api/start` | `{"camera_index": 0}` — start tracking |
| `POST` | `/api/pause` | Pause and release camera |
| `POST` | `/api/reset` | Reset cumulative counter |
| `POST` | `/api/camera` | `{"camera_index": 1}` — switch camera |
| `WS` | `/ws/stream` | Live frames + metrics |

WebSocket message format:

```json
{
  "type": "frame",
  "image": "<base64 JPEG>",
  "metrics": {
    "current_count": 2,
    "cumulative_count": 15,
    "fps": 18.4,
    "status": "running",
    "camera_index": 0,
    "is_running": true
  }
}
```

## Camera fallback (Windows)

`app/camera.py` tries:

- Indices **0, 1, 2** (preferred index first)
- Backends: **`cv2.CAP_DSHOW`** then default

This handles common Windows webcam issues with the MSMF backend.

## Project structure

```
people-counter/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI + WebSocket
│   │   ├── tracker_service.py # YOLO + ByteTrack loop
│   │   ├── camera.py         # Webcam open/fallback/release
│   │   ├── metrics.py        # Headcount state
│   │   └── config.py         # Model & tuning constants
│   ├── bytetrack.yaml        # ByteTrack parameters
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/       # VideoStream, StatCards, ControlPanel
│   │   ├── hooks/            # WebSocket + REST controls
│   │   └── styles/
│   └── package.json
└── README.md
```

## Production notes

- Set `allow_origins` in `main.py` to your frontend domain.
- Use a process manager (systemd, Docker) for `uvicorn`.
- Build frontend: `npm run build` and serve `dist/` via nginx or mount in FastAPI.
- For GPU: install `torch` with CUDA before `ultralytics`.
- Tune `CONFIDENCE_THRESHOLD` and `bytetrack.yaml` for your room layout.

## License

MIT
# people-counter
