"""Where Sweepr keeps its files. Everything is per-user; nothing needs admin rights.

Overrides (all optional):
  SWEEPR_DATA_DIR   jobs and logs (default: platform user data dir)
  SWEEPR_CACHE_DIR  downloaded engine + ffmpeg (default: platform user cache dir)
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

APP_NAME = "Sweepr"
DEFAULT_PORT = 8765
PACKAGE_DIR = Path(__file__).resolve().parent
UI_DIST = PACKAGE_DIR / "ui" / "dist"


def data_dir(override: str | os.PathLike[str] | None = None) -> Path:
    raw = override or os.environ.get("SWEEPR_DATA_DIR") or user_data_dir(APP_NAME, appauthor=False)
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    raw = os.environ.get("SWEEPR_CACHE_DIR") or user_cache_dir(APP_NAME, appauthor=False)
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
