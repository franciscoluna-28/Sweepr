"""Job queue: on-disk job directories plus a single worker thread.

The manifest.json inside each job directory is the source of truth — no
database, no broker. The API thread writes jobs, the worker thread runs them,
and readers only ever see atomic (temp-file + rename) manifest swaps.
"""

import json
import os
import queue
import re
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import engine, limits

JOBS_DIR = Path(__file__).resolve().parent / "data" / "jobs"
_MANIFEST = "manifest.json"
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ACTIVE_STATUSES = ("queued", "running")

_queue: "queue.Queue[str | None]" = queue.Queue()
_lock = threading.Lock()
_cancels: dict[str, threading.Event] = {}
_running: str | None = None
_thread: threading.Thread | None = None


def is_valid_id(job_id: str) -> bool:
    return bool(_UUID_RE.match(job_id))


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def read_job(job_id: str) -> dict | None:
    path = job_dir(job_id) / _MANIFEST
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_job(job: dict) -> None:
    path = job_dir(job["id"]) / _MANIFEST
    tmp = path.with_name(".manifest.tmp")
    tmp.write_text(json.dumps(job, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def list_jobs() -> list[dict]:
    if not JOBS_DIR.is_dir():
        return []
    jobs = []
    for path in JOBS_DIR.iterdir():
        if path.is_dir() and is_valid_id(path.name):
            job = read_job(path.name)
            if job:
                jobs.append(job)
    jobs.sort(key=lambda j: j.get("created", ""), reverse=True)
    return jobs


def purge_job(job_id: str) -> None:
    shutil.rmtree(job_dir(job_id), ignore_errors=True)


def can_accept() -> bool:
    with _lock:
        return _running is None and _queue.qsize() < limits.MAX_WAITING_JOBS


def enqueue(job_id: str) -> bool:
    with _lock:
        if _running is not None or _queue.qsize() >= limits.MAX_WAITING_JOBS:
            return False
        _cancels[job_id] = threading.Event()
        _queue.put(job_id)
        return True


def request_delete(job_id: str, status: str) -> str:
    """Cancel-and-purge. Returns ``purged`` or ``cancelling`` (worker owns it)."""
    with _lock:
        event = _cancels.get(job_id)
        if event:
            event.set()
    if status != "running":
        purge_job(job_id)
        return "purged"
    return "cancelling"


def _run_job(job_id: str) -> None:
    if not job_dir(job_id).is_dir():
        return
    cancel = _cancels.get(job_id) or threading.Event()
    job = read_job(job_id)
    if job is None:
        return
    job["status"] = "running"
    write_job(job)

    cancelled = False
    for i, entry in enumerate(job["files"]):
        if cancel.is_set():
            cancelled = True
            break
        entry["status"] = "processing"
        write_job(job)
        src = job_dir(job_id) / entry["stored"]
        dst = job_dir(job_id) / "out" / f"{i:02d}.wav"
        try:
            video = engine.process_file(str(src), str(dst), job["settings"])
            entry.update(status="done", error=None, video=None)
            if video:
                entry["video"] = f"out/{os.path.basename(video)}"
        except engine.AudioError as e:
            entry.update(status="error", error=str(e))
        except Exception as e:
            entry.update(status="error", error=f"processing failed: {e}")
        write_job(job)

    if cancelled or cancel.is_set():
        purge_job(job_id)
        return
    statuses = {f["status"] for f in job["files"]}
    job["status"] = "done_with_errors" if "error" in statuses else "done"
    write_job(job)


def _worker_loop() -> None:
    global _running
    while True:
        job_id = _queue.get()
        if job_id is None:
            return
        with _lock:
            _running = job_id
        try:
            _run_job(job_id)
        finally:
            with _lock:
                _running = None
            _cancels.pop(job_id, None)
            _queue.task_done()


def start_worker() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_worker_loop, name="job-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    _queue.put(None)


def recover() -> None:
    """At startup: prune old jobs, mark anything half-done as interrupted."""
    if not JOBS_DIR.is_dir():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=limits.RETENTION_DAYS)
    for path in list(JOBS_DIR.iterdir()):
        if not path.is_dir() or not is_valid_id(path.name):
            shutil.rmtree(path, ignore_errors=True)
            continue
        job = read_job(path.name)
        if job is None:
            purge_job(path.name)
            continue
        try:
            created = datetime.fromisoformat(job["created"])
        except (KeyError, ValueError):
            purge_job(path.name)
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            purge_job(path.name)
            continue
        if job.get("status") in ACTIVE_STATUSES:
            job["status"] = "interrupted"
            for f in job["files"]:
                if f.get("status") in ("queued", "processing"):
                    f["status"] = "error"
                    f["error"] = "server restarted before this file finished"
            write_job(job)
