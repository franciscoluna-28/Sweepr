"""Run the host-side audio bridge (native Windows process).

    .venv\\Scripts\\python.exe audio_bridge.py

Exposes the record-mode API on port 8766 so the Docker container can reach the
host audio devices through http://host.docker.internal:8766.
"""

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("MEOWLESS_BRIDGE_HOST", "0.0.0.0")
    port = int(os.environ.get("MEOWLESS_BRIDGE_PORT", "8766"))
    uvicorn.run("app.bridge:app", host=host, port=port, log_level="info")
