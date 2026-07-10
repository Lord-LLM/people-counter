FROM python:3.11-slim

WORKDIR /app

# System libraries required by OpenCV and Ultralytics at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached when only app code changes).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLO11n weights during build so cold starts skip the download.
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

# Copy application source after deps/weights to maximize cache hits.
COPY . .

# Non-root user for production security.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Render injects $PORT at runtime; default 10000 for local `docker run` without -e PORT.
EXPOSE 10000

# Shell form required — JSON-array CMD does not expand $PORT.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
