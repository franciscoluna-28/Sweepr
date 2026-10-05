"""Host-side audio bridge for the Docker deployment.

Docker Desktop on Windows runs a Linux VM that cannot see Windows audio
devices, so the container cannot capture or play audio itself. Run this
bridge natively on the host (same venv) and point the container at it:

    .venv\\Scripts\\python.exe audio_bridge.py

Then in docker-compose the API gets:

    MEOWLESS_AUDIO_BRIDGE=http://host.docker.internal:8766

The bridge owns the real audio devices and runs DeepFilterNet; the container
only serves the UI/API and forwards record-mode requests here.
"""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import engine, virtualmic

app = FastAPI(title="Meowless Audio Bridge", version="0.1.0")


@app.on_event("startup")
def _startup():
    engine.warmup()


class SessionStart(BaseModel):
    input_id: int
    output_id: int
    input_name: str | None = None
    output_name: str | None = None
    atten_lim_db: float = 100.0
    post_filter: bool = False
    block: int = 960


class SessionUpdate(BaseModel):
    atten_lim_db: float | None = None
    post_filter: bool | None = None
    input_id: int | None = None
    output_id: int | None = None
    input_name: str | None = None
    output_name: str | None = None
    block: int | None = None


def _resolve(input_id, output_id, input_name, output_name):
    if input_name:
        found = virtualmic.resolve_device(input_name, "in")
        if found is not None:
            input_id = found
    if output_name:
        found = virtualmic.resolve_device(output_name, "out")
        if found is not None:
            output_id = found
    return input_id, output_id


@app.get("/devices")
def devices():
    data = virtualmic.list_devices()
    data["available"] = True
    data["reason"] = None
    return data


@app.get("/session/status")
def session_status():
    return virtualmic.service.status()


@app.post("/session/start")
async def session_start(body: SessionStart):
    in_id, out_id = _resolve(
        body.input_id, body.output_id, body.input_name, body.output_name
    )
    try:
        virtualmic.service.start(
            in_id, out_id, body.atten_lim_db, body.post_filter, body.block
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return virtualmic.service.status()


@app.post("/session/stop")
async def session_stop():
    virtualmic.service.stop()
    return virtualmic.service.status()


@app.patch("/session")
async def session_update(body: SessionUpdate):
    in_id, out_id = _resolve(
        body.input_id, body.output_id, body.input_name, body.output_name
    )
    try:
        virtualmic.service.update(
            body.atten_lim_db, body.post_filter, in_id, out_id, body.block
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return virtualmic.service.status()


@app.post("/session/start")
def session_start(body: SessionStart):
    try:
        virtualmic.service.start(
            body.input_id,
            body.output_id,
            body.atten_lim_db,
            body.post_filter,
            body.block,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return virtualmic.service.status()


@app.post("/session/stop")
def session_stop():
    virtualmic.service.stop()
    return virtualmic.service.status()


@app.patch("/session")
def session_update(body: SessionUpdate):
    try:
        virtualmic.service.update(
            body.atten_lim_db,
            body.post_filter,
            body.input_id,
            body.output_id,
            body.block,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return virtualmic.service.status()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("MEOWLESS_BRIDGE_PORT", "8766"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
