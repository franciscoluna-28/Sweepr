import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import engine

try:
    from . import virtualmic
except Exception:  # e.g. no PortAudio in a container
    virtualmic = None  # type: ignore

# Optional host-side audio bridge (see audio_bridge.py). Used when the app
# runs in Docker and therefore cannot reach the host's audio devices.
BRIDGE = os.environ.get("MEOWLESS_AUDIO_BRIDGE", "").rstrip("/")

UI_DIST = Path(__file__).resolve().parent / "ui" / "dist"

app = FastAPI(
    title="Meowless",
    description=(
        "Single-process app that removes background noise from audio with "
        "DeepFilterNet. The Svelte UI is served by this same app and calls "
        "these endpoints with plain `fetch` — no generated clients."
    ),
    version="0.1.0",
)


@app.on_event("startup")
def _startup():
    engine.warmup()


@app.get("/api/health", tags=["system"], summary="Service and model status")
def health():
    """Whether the server is up and which models are loaded in memory."""
    return {"status": "ok", "models_loaded": list(engine._models.keys())}


@app.post("/api/enhance", tags=["audio"], summary="Denoise an audio file")
async def enhance_endpoint(
    file: UploadFile = File(..., description="Audio file to denoise."),
    atten_lim_db: float = Form(
        100.0,
        description="Noise attenuation limit in dB (0 = off, 100 = max suppression).",
    ),
    post_filter: bool = Form(False, description="Over-attenuate very noisy sections."),
):
    """Decode, resample to 48 kHz, enhance, and return a 16-bit WAV."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        out = engine.enhance_bytes(
            data, file.filename or "input.wav", atten_lim_db, post_filter
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    name = os.path.splitext(file.filename or "output.wav")[0] + "_enhanced.wav"
    return Response(
        content=out,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ── Record mode (virtual microphone) ────────────────────────────────────────
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


def _resolve_ids(input_id, output_id, input_name, output_name):
    """Prefer name-based lookup so device-index drift doesn't pick the wrong
    device (PortAudio indices shift when devices are plugged/unplugged)."""
    if virtualmic is None:
        return input_id, output_id
    if input_name:
        found = virtualmic.resolve_device(input_name, "in")
        if found is not None:
            input_id = found
    if output_name:
        found = virtualmic.resolve_device(output_name, "out")
        if found is not None:
            output_id = found
    return input_id, output_id


def _unavailable(reason: str) -> dict:
    return {
        "inputs": [],
        "outputs": [],
        "virtual_cable": None,
        "available": False,
        "reason": reason,
    }


def _bridge(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BRIDGE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _bridge_error(e: Exception) -> HTTPException:
    if isinstance(e, urllib.error.HTTPError):
        detail = e.read().decode(errors="replace") or e.reason
        return HTTPException(status_code=e.code, detail=detail)
    return HTTPException(status_code=502, detail=f"Audio bridge error: {e}")


@app.get("/api/devices", tags=["record"], summary="List audio input/output devices")
def devices():
    if virtualmic is not None:
        data = virtualmic.list_devices()
        data["available"] = True
        data["reason"] = None
        return data
    if BRIDGE:
        try:
            data = _bridge("GET", "/devices")
            data["available"] = True
            data["reason"] = None
            return data
        except Exception as e:
            return _unavailable(f"Audio bridge unreachable at {BRIDGE} ({e}).")
    return _unavailable(
        "Audio devices are unavailable in this container. Run the host audio "
        "bridge (python audio_bridge.py) and set MEOWLESS_AUDIO_BRIDGE."
    )


@app.post("/api/session/start", tags=["record"], summary="Start the virtual microphone")
async def session_start(body: SessionStart):
    if virtualmic is not None:
        in_id, out_id = _resolve_ids(
            body.input_id, body.output_id, body.input_name, body.output_name
        )
        try:
            virtualmic.service.start(
                in_id,
                out_id,
                body.atten_lim_db,
                body.post_filter,
                body.block,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return virtualmic.service.status()
    if BRIDGE:
        try:
            return await run_in_threadpool(
                _bridge, "POST", "/session/start", body.model_dump()
            )
        except Exception as e:
            raise _bridge_error(e)
    raise HTTPException(status_code=503, detail="Audio devices unavailable")


@app.post("/api/session/stop", tags=["record"], summary="Stop the virtual microphone")
async def session_stop():
    if virtualmic is not None:
        virtualmic.service.stop()
        return virtualmic.service.status()
    if BRIDGE:
        try:
            return await run_in_threadpool(_bridge, "POST", "/session/stop")
        except Exception as e:
            raise _bridge_error(e)
    raise HTTPException(status_code=503, detail="Audio devices unavailable")


@app.patch("/api/session", tags=["record"], summary="Update the running session")
async def session_update(body: SessionUpdate):
    if virtualmic is not None:
        in_id, out_id = _resolve_ids(
            body.input_id, body.output_id, body.input_name, body.output_name
        )
        try:
            virtualmic.service.update(
                body.atten_lim_db,
                body.post_filter,
                in_id,
                out_id,
                body.block,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return virtualmic.service.status()
    if BRIDGE:
        try:
            return await run_in_threadpool(
                _bridge, "PATCH", "/session", body.model_dump()
            )
        except Exception as e:
            raise _bridge_error(e)
    raise HTTPException(status_code=503, detail="Audio devices unavailable")


@app.get("/api/session/status", tags=["record"], summary="Virtual microphone status")
def session_status():
    if virtualmic is not None:
        return virtualmic.service.status()
    if BRIDGE:
        try:
            return _bridge("GET", "/session/status")
        except Exception:
            return {"running": False, "error": "Audio bridge unreachable"}
    return {"running": False, "error": "Audio devices unavailable"}


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")
else:

    @app.get("/")
    def _no_build():
        return {
            "detail": "UI not built. Run `pnpm build` inside app/ui, "
            "or use the Vite dev server."
        }
