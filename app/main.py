import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from . import engine

UI_DIST = Path(__file__).resolve().parent / "ui" / "dist"

app = FastAPI(
    title="DeepFilterNet Denoiser",
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


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")
else:

    @app.get("/")
    def _no_build():
        return {
            "detail": "UI not built. Run `pnpm build` inside app/ui, "
            "or use the Vite dev server."
        }
