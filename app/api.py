"""HTTP API: job routes with server-side validation. Wiring only, no DSP."""

import math
import mimetypes
import os
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from . import engine, jobs, limits

router = APIRouter(prefix="/api", tags=["jobs"])


class _TooLarge(Exception):
    pass


def _reject(message: str, errors: list[str] | None = None):
    raise HTTPException(400, detail={"message": message, "errors": errors or [message]})


def _require_valid(job_id: str) -> dict:
    if not jobs.is_valid_id(job_id):
        raise HTTPException(404, "job not found")
    job = jobs.read_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


def _safe_name(raw: str | None, fallback: str) -> str:
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = "".join(
        ch if ch.isprintable() and ch not in '<>:"|?*' else "_" for ch in name
    )
    name = name.strip(" .")
    return name[:120] or fallback


async def _save(upload: UploadFile, dest, total_so_far: int) -> int:
    """Stream one upload to disk, enforcing per-file and job-total caps."""
    written = 0
    remaining = limits.MAX_TOTAL_BYTES - total_so_far
    with open(dest, "wb") as out:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            if written > limits.MAX_FILE_BYTES:
                raise _TooLarge(f"larger than {limits.MAX_FILE_BYTES // 1048576} MB")
            if written > remaining:
                raise _TooLarge(
                    f"job exceeds {limits.MAX_TOTAL_BYTES // 1048576} MB in total"
                )
            out.write(chunk)
    return written


@router.get("/health", summary="Service, model, and limit status")
def health():
    return {
        "status": "ok",
        "models_loaded": list(engine._models.keys()),
        "limits": {
            "max_files": limits.MAX_FILES,
            "max_file_mb": limits.MAX_FILE_BYTES // 1048576,
            "max_total_mb": limits.MAX_TOTAL_BYTES // 1048576,
            "max_duration_min": limits.MAX_DURATION_S // 60,
            "allowed_exts": sorted(e.lstrip(".") for e in limits.ALLOWED_EXTS),
        },
    }


@router.post("/jobs", status_code=202, summary="Create a batch job")
async def create_job(
    files: list[UploadFile] = File(...),
    atten_lim_db: float = Form(limits.DEFAULT_ATTEN_DB),
    post_filter: bool = Form(False),
):
    errors: list[str] = []
    if not 0 < len(files) <= limits.MAX_FILES:
        errors.append(f"send 1 to {limits.MAX_FILES} files (got {len(files)})")
    if not math.isfinite(atten_lim_db) or not (
        limits.MIN_ATTEN_DB <= atten_lim_db <= limits.MAX_ATTEN_DB
    ):
        errors.append(
            f"atten_lim_db must be between {limits.MIN_ATTEN_DB:.0f} and {limits.MAX_ATTEN_DB:.0f}"
        )
    if errors:
        _reject("invalid job settings", errors)
    if not jobs.can_accept():
        raise HTTPException(429, "queue is full, try again in a moment")

    job_id = str(uuid.uuid4())
    dir_ = jobs.job_dir(job_id)
    (dir_ / "in").mkdir(parents=True)
    (dir_ / "out").mkdir()
    entries: list[dict] = []
    total = 0
    try:
        for i, upload in enumerate(files):
            name = _safe_name(upload.filename, f"file{i}")
            ext = os.path.splitext(name)[1].lower()
            if ext not in limits.ALLOWED_EXTS:
                allowed = ", ".join(sorted(e.lstrip(".") for e in limits.ALLOWED_EXTS))
                errors.append(f"{name}: unsupported format (allowed: {allowed})")
                continue
            stored = f"in/{i:02d}{ext}"
            dest = dir_ / stored
            try:
                total += await _save(upload, dest, total)
                engine.probe(str(dest))
            except _TooLarge as e:
                dest.unlink(missing_ok=True)
                errors.append(f"{name}: {e}")
                continue
            except engine.AudioError as e:
                dest.unlink(missing_ok=True)
                errors.append(f"{name}: {e}")
                continue
            entries.append(
                {
                    "name": name,
                    "stored": stored,
                    "status": "queued",
                    "error": None,
                    "video": None,
                }
            )
        if errors:
            _reject(f"{len(errors)} problem(s) with the upload", errors)
        jobs.write_job(
            {
                "id": job_id,
                "created": datetime.now(timezone.utc).isoformat(),
                "status": "queued",
                "settings": {
                    "atten_lim_db": atten_lim_db,
                    "post_filter": post_filter,
                },
                "files": entries,
            }
        )
    except BaseException:
        jobs.purge_job(job_id)
        raise
    if not jobs.enqueue(job_id):
        jobs.purge_job(job_id)
        raise HTTPException(429, "queue is full, try again in a moment")
    return {"job_id": job_id}


@router.get("/jobs", summary="List jobs, newest first")
def list_jobs():
    return jobs.list_jobs()


@router.get("/jobs/{job_id}", summary="Job status and per-file detail")
def get_job(job_id: str):
    return _require_valid(job_id)


@router.get(
    "/jobs/{job_id}/files/{index}",
    summary="Original, enhanced WAV, or muxed video",
)
def get_file(job_id: str, index: int, which: Literal["in", "out", "video"] = "in"):
    job = _require_valid(job_id)
    if not 0 <= index < len(job["files"]):
        raise HTTPException(404, "file not found")
    entry = job["files"][index]
    stem = os.path.splitext(entry["name"])[0]
    if which == "in":
        path = jobs.job_dir(job_id) / entry["stored"]
        name = entry["name"]
    else:
        if entry["status"] != "done":
            raise HTTPException(404, "result not ready")
        if which == "video":
            stored = entry.get("video")
            if not stored:
                raise HTTPException(404, "no video output for this file")
            path = jobs.job_dir(job_id) / stored
            name = stem + "_enhanced" + os.path.splitext(stored)[1]
        else:
            path = jobs.job_dir(job_id) / "out" / f"{index:02d}.wav"
            name = stem + "_enhanced.wav"
    if not path.is_file():
        raise HTTPException(404, "file not found")
    media = mimetypes.guess_type(name)[0] or (
        "audio/wav" if which == "out" else "application/octet-stream"
    )
    return FileResponse(path, media_type=media, filename=name)


@router.get("/jobs/{job_id}/zip", summary="All finished results as a zip")
def download_zip(job_id: str):
    job = _require_valid(job_id)
    done = [(i, f) for i, f in enumerate(job["files"]) if f["status"] == "done"]
    if not done:
        raise HTTPException(400, "no completed files to download yet")
    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    used: set[str] = set()

    def add(zf: zipfile.ZipFile, path, base: str, ext: str, suffix: str = "") -> None:
        arc = f"{base}{suffix}{ext}"
        n = 2
        while arc in used:
            arc = f"{base}{suffix} ({n}){ext}"
            n += 1
        used.add(arc)
        zf.write(path, arcname=arc)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
            for i, f in done:
                stem = os.path.splitext(f["name"])[0] or "audio"
                add(
                    zf,
                    jobs.job_dir(job_id) / "out" / f"{i:02d}.wav",
                    stem,
                    ".wav",
                    "_enhanced",
                )
                stored = f.get("video")
                if stored:
                    add(
                        zf,
                        jobs.job_dir(job_id) / stored,
                        stem,
                        os.path.splitext(stored)[1],
                        "_enhanced",
                    )
    except BaseException:
        os.remove(tmp_path)
        raise
    return FileResponse(
        tmp_path,
        media_type="application/zip",
        filename=f"meowless_{job_id[:8]}.zip",
        background=BackgroundTask(_remove, tmp_path),
    )


@router.delete("/jobs/{job_id}", summary="Cancel (if running) and delete a job")
def delete_job(job_id: str):
    job = _require_valid(job_id)
    if jobs.request_delete(job_id, job["status"]) == "cancelling":
        return Response(
            content='{"status": "cancelling"}',
            status_code=202,
            media_type="application/json",
        )
    return Response(status_code=204)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
