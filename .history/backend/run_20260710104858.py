"""Run the People Counter FastAPI server.

Read the port to bind from the environment variable `PORT` so container
platforms like Render can inject the assigned port. Falls back to 8000
for local development.
"""

import os
import uvicorn


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
