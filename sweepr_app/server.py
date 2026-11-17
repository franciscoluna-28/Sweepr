"""Application factory: routes, upload guard, security, and the bundled UI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, jobs, paths
from .api import router
from .limits import MAX_TOTAL_BYTES
from .security import SecurityMiddleware, allowed_hosts

_UPLOAD_SLACK = 1024 * 1024


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    token: str
    port: int = paths.DEFAULT_PORT
    trusted_hosts: tuple[str, ...] = field(default_factory=tuple)
    ui_dist: Path = paths.UI_DIST

    def __post_init__(self) -> None:
        # An empty token would make an empty X-Sweepr-Token header authorize.
        if not isinstance(self.token, str) or not self.token.strip():
            raise ValueError("access token must not be empty")


def _error_body(message: str, errors: list[str] | None = None) -> dict:
    """The one error envelope every non-2xx response uses (see schemas.ErrorEnvelope)."""
    return {"detail": {"message": message, "errors": errors or [message]}}


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        jobs.configure(settings.data_dir / "jobs")
        jobs.recover()
        jobs.start_worker()
        yield
        jobs.stop_worker()

    app = FastAPI(
        title="Sweepr",
        description=(
            "Local, single-user app that removes background noise from audio and video "
            "with DeepFilterNet. Files never leave the machine. Every /api route except "
            "/api/health requires the per-launch access token."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "message" in detail:
            message = str(detail["message"])
            raw = detail.get("errors")
            errors = [str(e) for e in raw] if isinstance(raw, list) else [str(raw) if raw else message]
        else:
            message = str(detail)
            errors = [message]
        return JSONResponse(_error_body(message, errors), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            f"{'/'.join(str(part) for part in err.get('loc', ()))}: {err.get('msg', 'invalid')}"
            for err in exc.errors()
        ]
        return JSONResponse(_error_body("invalid request", errors), status_code=422)

    @app.middleware("http")
    async def upload_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Reject oversized batch uploads before a single byte is buffered."""
        if request.method == "POST" and request.url.path == "/api/jobs":
            length = request.headers.get("content-length")
            if length is None:
                return JSONResponse(_error_body("Content-Length required"), status_code=411)
            try:
                too_big = int(length) > MAX_TOTAL_BYTES + _UPLOAD_SLACK
            except ValueError:
                return JSONResponse(_error_body("invalid Content-Length"), status_code=400)
            if too_big:
                return JSONResponse(_error_body("job upload too large"), status_code=413)
        return await call_next(request)

    # Added last so it runs first: nothing reaches the routes unchecked.
    app.add_middleware(
        SecurityMiddleware,
        token=settings.token,
        hosts=allowed_hosts(settings.port, settings.trusted_hosts),
    )

    app.include_router(router)

    if settings.ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(settings.ui_dist), html=True), name="ui")
    else:

        @app.get("/", include_in_schema=False)
        def _no_build() -> dict:
            return {"detail": "The Sweepr UI is not built. Run `pnpm --dir sweepr_app/ui build`."}

    return app
