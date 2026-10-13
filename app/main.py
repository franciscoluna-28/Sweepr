"""Application factory: router, upload guard, static UI, lifecycle hooks."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import engine, jobs
from .api import router
from .limits import MAX_TOTAL_BYTES

UI_DIST = Path(__file__).resolve().parent / "ui" / "dist"
_UPLOAD_SLACK = 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.warmup()
    jobs.recover()
    jobs.start_worker()
    yield
    jobs.stop_worker()


app = FastAPI(
    title="Sweepr",
    description=(
        "Local, single-process app that removes background noise from audio "
        "files with DeepFilterNet. Files never leave the machine. The Svelte "
        "UI is served by this same app; every run — even a single file — is a "
        "job."
    ),
    version="0.3.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def upload_guard(request: Request, call_next):
    """Reject oversized batch uploads before a single byte is buffered."""
    if request.method == "POST" and request.url.path == "/api/jobs":
        length = request.headers.get("content-length")
        if length is None:
            return JSONResponse({"detail": "Content-Length required"}, status_code=411)
        try:
            too_big = int(length) > MAX_TOTAL_BYTES + _UPLOAD_SLACK
        except ValueError:
            return JSONResponse({"detail": "invalid Content-Length"}, status_code=400)
        if too_big:
            return JSONResponse({"detail": "job upload too large"}, status_code=413)
    return await call_next(request)


app.include_router(router)

if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")
else:

    @app.get("/")
    def _no_build():
        return {
            "detail": "UI not built. Run `pnpm build` inside app/ui, "
            "or use the Vite dev server."
        }
