"""Pydantic models describing the HTTP API.

These are the single source of truth for what the routes return (and what the
UI types are generated from). The on-disk job manifests are plain dicts; the
response models below validate and serialize them on the way out.
"""

from typing import Literal

from pydantic import BaseModel

JobStatus = Literal["queued", "running", "done", "done_with_errors", "interrupted"]
FileStatus = Literal["queued", "processing", "done", "error"]


class JobSettings(BaseModel):
    atten_lim_db: float
    post_filter: bool
    normalize: bool = False
    target_lufs: float = -14.0


class JobFile(BaseModel):
    name: str
    stored: str
    status: FileStatus
    error: str | None = None
    video: str | None = None
    lufs_before: float | None = None
    lufs_after: float | None = None


class Job(BaseModel):
    id: str
    created: str
    status: JobStatus
    settings: JobSettings
    files: list[JobFile]


class Limits(BaseModel):
    max_files: int
    max_file_mb: int
    max_total_mb: int
    max_duration_min: int
    allowed_exts: list[str]
    normalize_targets: list[float]
    target_lufs_range: list[float]
    true_peak_dbtp: float


class Health(BaseModel):
    status: str
    models_loaded: list[bool]
    limits: Limits


class CreateJobResponse(BaseModel):
    job_id: str


class DeleteJobResponse(BaseModel):
    status: Literal["cancelling"]


class ErrorDetail(BaseModel):
    message: str
    errors: list[str]


class ErrorEnvelope(BaseModel):
    """The single error shape every non-2xx response uses."""

    detail: ErrorDetail
