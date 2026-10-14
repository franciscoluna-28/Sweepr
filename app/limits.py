"""Hard limits and allowlists — enforced on the server, mirrored by the UI via /api/health.

Every value below is overridable with a ``SWEEPR_*`` environment variable
(``SWEEPR_PORT`` also falls back to the platform-standard ``PORT``), so one
image can be tuned per deployment. Invalid values fail fast at import with a
message naming the variable. Byte sizes accept plain integers (bytes) or
human suffixes: ``5120M``, ``5G``, ``5GiB``.

Format-related allowlists (extensions, sample rates, channels, atten dB) are
product decisions, not deployment knobs — they stay hardcoded.
"""

import os
import re
from pathlib import Path

_PREFIX = "SWEEPR_"

_BYTES_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([kmgt]i?b?|b)?$", re.IGNORECASE)
_BYTE_UNITS = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}


def _env(name: str) -> str | None:
    raw = os.environ.get(_PREFIX + name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _int_env(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError:
        raise ValueError(
            f"{_PREFIX}{name} must be an integer, got {raw!r}"
        ) from None
    if value < minimum or (maximum is not None and value > maximum):
        bound = (
            f"between {minimum} and {maximum}"
            if maximum is not None
            else f"at least {minimum}"
        )
        raise ValueError(f"{_PREFIX}{name} must be {bound}, got {value}")
    return value


def _bytes_env(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    match = _BYTES_RE.match(raw)
    if not match:
        raise ValueError(
            f"{_PREFIX}{name} must be a byte count like '5368709120' "
            f"or a size like '5120M' or '5G', got {raw!r}"
        )
    unit = (match.group(2) or "").lower().rstrip("ib")
    value = int(float(match.group(1)) * _BYTE_UNITS[unit])
    if value < 1:
        raise ValueError(f"{_PREFIX}{name} must be at least 1 byte, got {value}")
    return value


def _path_env(name: str, default: Path) -> Path:
    raw = _env(name)
    if raw is None:
        return default
    return Path(raw).expanduser().resolve()


def _port() -> int:
    """SWEEPR_PORT first, then the platform-standard PORT (Cloud Run, Fly…), else 8765."""
    for var in (_PREFIX + "PORT", "PORT"):
        raw = os.environ.get(var)
        if raw is None or not raw.strip():
            continue
        raw = raw.strip()
        try:
            value = int(raw, 10)
        except ValueError:
            raise ValueError(
                f"{var} must be an integer between 1 and 65535, got {raw!r}"
            ) from None
        if not 1 <= value <= 65535:
            raise ValueError(f"{var} must be between 1 and 65535, got {value}")
        return value
    return 8765


MAX_FILES = _int_env("MAX_FILES", 10, minimum=1)
MAX_FILE_BYTES = _bytes_env("MAX_FILE_BYTES", 5 * 1024 * 1024 * 1024)
MAX_TOTAL_BYTES = _bytes_env("MAX_TOTAL_BYTES", 10 * 1024 * 1024 * 1024)
MAX_DURATION_S = _int_env("MAX_DURATION_S", 4 * 60 * 60, minimum=1)
MIN_SAMPLE_RATE = 8000
MAX_SAMPLE_RATE = 192000
MAX_CHANNELS = 2

MAX_WAITING_JOBS = _int_env("MAX_WAITING_JOBS", 3, minimum=1)
RETENTION_DAYS = _int_env("RETENTION_DAYS", 7, minimum=0)

PORT = _port()
JOBS_DIR = _path_env("JOBS_DIR", Path(__file__).resolve().parent / "data" / "jobs")

if MAX_FILE_BYTES > MAX_TOTAL_BYTES:
    raise ValueError(
        f"{_PREFIX}MAX_FILE_BYTES ({MAX_FILE_BYTES}) must not exceed "
        f"{_PREFIX}MAX_TOTAL_BYTES ({MAX_TOTAL_BYTES})"
    )

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
ALLOWED_EXTS = AUDIO_EXTS | VIDEO_EXTS

MIN_ATTEN_DB = 0.0
MAX_ATTEN_DB = 100.0
DEFAULT_ATTEN_DB = 25.0

# Post-denoise loudness normalization (opt-in). Targets are EBU R128 integrated
# loudness in LUFS; the true-peak ceiling keeps inter-sample overs in check.
MIN_TARGET_LUFS = -24.0
MAX_TARGET_LUFS = -9.0
DEFAULT_TARGET_LUFS = -14.0
DEFAULT_TRUE_PEAK_DBTP = -1.0
LUFS_PRESETS = (-14.0, -16.0)
