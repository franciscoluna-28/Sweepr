import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from backend import df_engine

app = FastAPI(title="DeepFilterNet Denoiser")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@app.on_event("startup")
def _startup():
    df_engine.warmup()


@app.get("/api/health")
def health():
    return {"status": "ok", "models_loaded": list(df_engine._models.keys())}


@app.post("/api/enhance")
async def enhance_endpoint(
    file: UploadFile = File(...),
    atten_lim_db: float = Form(100.0),
    post_filter: bool = Form(False),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        out = df_engine.enhance_bytes(
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


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="static")
