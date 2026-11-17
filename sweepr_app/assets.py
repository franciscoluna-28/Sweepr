"""The engine and ffmpeg: pinned, checksummed, downloaded once and cached.

Sweepr never runs code it has not verified. Each platform pins either a complete
engine archive (deep-filter + ffmpeg + ffprobe, built by our release pipeline) or
the upstream ``deep-filter`` binary and ffmpeg archive, all with SHA-256
checksums in ``assets_manifest.json``. Downloads go to a temp file, are verified,
extracted into a staging directory, then moved into the cache.

Resolution order for the tools:
  1. SWEEPR_BIN_DIR, if set (offline installs, development, air-gapped use)
  2. the verified cache under ``paths.cache_dir()``
  3. system ffmpeg/ffprobe on PATH when the engine does not bundle them (macOS),
     or when SWEEPR_USE_SYSTEM_FFMPEG is set
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import __version__, paths

MANIFEST_PATH = Path(__file__).with_name("assets_manifest.json")
ENV_BIN_DIR = "SWEEPR_BIN_DIR"
ENV_BASE_URL = "SWEEPR_ASSET_BASE_URL"
ENV_SYSTEM_FFMPEG = "SWEEPR_USE_SYSTEM_FFMPEG"
MARKER = ".installed.json"
LOCK_STALE_S = 900
LOCK_WAIT_S = 300
DOWNLOAD_TIMEOUT_S = 60
CHUNK = 1 << 20

Progress = Callable[[int, int | None], None]


class AssetError(RuntimeError):
    """A user-facing problem with the engine assets (message is safe to show)."""


@dataclass(frozen=True)
class Tools:
    deep_filter: Path
    ffmpeg: Path
    ffprobe: Path

    def as_list(self) -> list[Path]:
        return [self.deep_filter, self.ffmpeg, self.ffprobe]


def _exe(name: str) -> str:
    return name + ".exe" if sys.platform == "win32" else name


def _is_library(name: str) -> bool:
    lower = name.lower()
    return lower.endswith((".dll", ".dylib")) or ".so" in lower


def _tools_in(directory: Path) -> Tools:
    return Tools(
        deep_filter=directory / _exe("deep-filter"),
        ffmpeg=directory / _exe("ffmpeg"),
        ffprobe=directory / _exe("ffprobe"),
    )


def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def platform_key() -> str:
    system = sys.platform
    machine = platform.machine().lower()
    if system == "win32" and machine in ("amd64", "x86_64"):
        return "windows-x86_64"
    if system == "darwin" and machine in ("arm64", "aarch64"):
        return "macos-arm64"
    if system == "darwin" and machine in ("x86_64", "amd64"):
        return "macos-x86_64"
    if system.startswith("linux") and machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    raise AssetError(f"Sweepr has no engine build for {system}/{machine} yet.")


def _platform_entry(key: str) -> dict:
    entry = manifest()["platforms"].get(key)
    if entry is None:
        raise AssetError(f"this Sweepr release has no engine build for {key}.")
    return entry


def install_dir(key: str | None = None) -> Path:
    version = manifest()["version"]
    return paths.cache_dir() / "assets" / version / (key or platform_key())


def _base_url() -> str:
    return (os.environ.get(ENV_BASE_URL) or manifest()["base_url"]).rstrip("/")


def _pin_sha(entry: dict) -> str | None:
    """The checksum that identifies this install (archive or upstream deep-filter)."""
    return entry.get("sha256") or (entry.get("deep_filter") or {}).get("sha256")


def _is_installed(directory: Path, entry: dict) -> bool:
    expected = _pin_sha(entry)
    marker = directory / MARKER
    if not marker.is_file() or not expected:
        return False
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError):
        return False
    if recorded != expected:
        return False
    tools = _tools_in(directory)
    if not tools.deep_filter.is_file():
        return False
    if entry.get("sha256"):
        return tools.ffmpeg.is_file() and tools.ffprobe.is_file()
    if entry.get("ffmpeg"):
        return tools.ffmpeg.is_file() and tools.ffprobe.is_file()
    return True


def _system_ffmpeg(tools: Tools) -> Tools:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise AssetError(
            "ffmpeg and ffprobe are required. Install them (on macOS: "
            "`brew install ffmpeg`) or set SWEEPR_BIN_DIR to a folder that has them."
        )
    return Tools(tools.deep_filter, Path(ffmpeg), Path(ffprobe))


def resolve_tools() -> Tools:
    """Find the engine tools without touching the network. Raises AssetError."""
    bin_dir = os.environ.get(ENV_BIN_DIR)
    if bin_dir:
        tools = _tools_in(Path(bin_dir).expanduser())
        if not tools.deep_filter.is_file():
            raise AssetError(f"{ENV_BIN_DIR} does not contain deep-filter.")
    else:
        entry = _platform_entry(platform_key())
        directory = install_dir()
        if not _is_installed(directory, entry):
            raise AssetError(
                "the engine is not installed yet. Start Sweepr once to download it "
                "(see `sweepr doctor`)."
            )
        tools = _tools_in(directory)

    if os.environ.get(ENV_SYSTEM_FFMPEG) or not (tools.ffmpeg.is_file() and tools.ffprobe.is_file()):
        tools = _system_ffmpeg(tools)
    return tools


def is_ready() -> bool:
    try:
        resolve_tools()
    except AssetError:
        return False
    return True


def ensure_tools(progress: Progress | None = None) -> Tools:
    """Like resolve_tools(), but downloads and verifies the engine when missing."""
    try:
        return resolve_tools()
    except AssetError:
        if os.environ.get(ENV_BIN_DIR):
            raise
    install(progress)
    return resolve_tools()


def _remove_tree(path: Path) -> None:
    """Remove a directory, retrying briefly for Windows file locks."""
    for _ in range(5):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.4)
    shutil.rmtree(path)


def install(progress: Progress | None = None) -> Path:
    """Download, verify and install the engine for this platform into the cache."""
    key = platform_key()
    entry = _platform_entry(key)
    expected = _pin_sha(entry)
    if not expected:
        raise AssetError(f"this Sweepr release has no engine pins for {key}.")
    dest = install_dir(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _lock(dest.with_name(dest.name + ".lock")):
        if _is_installed(dest, entry):
            return dest
        with tempfile.TemporaryDirectory(dir=dest.parent, ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            staging = tmp_path / "staging"
            staging.mkdir()
            if entry.get("sha256"):
                archive = tmp_path / entry["file"]
                _download(f"{_base_url()}/{entry['file']}", archive, entry["sha256"], entry.get("size"), progress)
                _extract(archive, staging)
            else:
                _install_upstream(entry, staging, tmp_path, progress)
            tools = _tools_in(staging)
            if not tools.deep_filter.is_file():
                raise AssetError("the downloaded engine is incomplete.")
            if entry.get("ffmpeg") and not (tools.ffmpeg.is_file() and tools.ffprobe.is_file()):
                raise AssetError("the downloaded ffmpeg build is incomplete.")
            if sys.platform != "win32":
                for tool in tools.as_list():
                    if tool.is_file():
                        tool.chmod(0o755)
            if dest.exists():
                _remove_tree(dest)
            shutil.move(str(staging), str(dest))
        (dest / MARKER).write_text(
            json.dumps(
                {
                    "version": manifest()["version"],
                    "platform": key,
                    "sha256": expected,
                    "source": "archive" if entry.get("sha256") else "upstream",
                    "ffmpeg_sha256": (entry.get("ffmpeg") or {}).get("sha256"),
                }
            ),
            encoding="utf-8",
        )
    return dest


def _install_upstream(entry: dict, staging: Path, tmp_path: Path, progress: Progress | None) -> None:
    """Fetch the pinned upstream deep-filter binary and (where available) ffmpeg."""
    pin = entry["deep_filter"]
    target = staging / _exe("deep-filter")
    _download(pin["url"], target, pin["sha256"], pin.get("size"), progress)
    if sys.platform != "win32":
        target.chmod(0o755)

    ffmpeg = entry.get("ffmpeg")
    if not ffmpeg:
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            raise AssetError(
                "ffmpeg and ffprobe are required on this platform. Install ffmpeg "
                "(on macOS: `brew install ffmpeg`) and retry."
            )
        return

    archive = tmp_path / Path(ffmpeg["url"]).name
    _download(ffmpeg["url"], archive, ffmpeg["sha256"], ffmpeg.get("size"), None)
    _extract_ffmpeg(archive, ffmpeg.get("kind", "zip"), staging, tmp_path)


def _extract_ffmpeg(archive: Path, kind: str, dest: Path, workdir: Path) -> None:
    root = workdir / "ffmpeg"
    root.mkdir()
    if kind == "zip":
        _extract_zip(archive, root)
    else:
        _extract_tar(archive, root)

    top = next((p for p in root.iterdir() if p.is_dir()), root)
    names = (f"ffmpeg{_exe('')}", f"ffprobe{_exe('')}")
    for name in names:
        found = next(
            (directory / name for directory in (top / "bin", top, top / "lib") if (directory / name).is_file()),
            None,
        )
        if found is None:
            raise AssetError(f"{name} was not in the ffmpeg archive.")
        shutil.copy2(found, dest / name)

    for directory in (top / "bin", top / "lib", top):
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.name not in names and _is_library(path.name):
                shutil.copy2(path, dest / path.name)


def _extract_zip(archive: Path, dest: Path) -> None:
    root = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(root):
                raise AssetError(f"unexpected path in engine archive: {info.filename!r}")
            zf.extract(info, dest)


def _extract_tar(archive: Path, dest: Path) -> None:
    root = dest.resolve()
    with tarfile.open(archive, "r:xz") as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:  # Python < 3.11.4
            for member in tf.getmembers():
                target = (dest / member.name).resolve()
                if not target.is_relative_to(root):
                    raise AssetError(f"unexpected path in engine archive: {member.name!r}")
                if member.issym() or member.islnk():
                    link = (target.parent / member.linkname).resolve()
                    if not link.is_relative_to(root):
                        raise AssetError(f"unexpected link in engine archive: {member.name!r}")
            tf.extractall(dest)


def _download(url: str, dest: Path, sha256: str, size: int | None, progress: Progress | None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": f"sweepr-app/{__version__}"})
    try:
        response = urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S)
    except (urllib.error.URLError, OSError) as exc:
        raise AssetError(
            f"could not download the engine ({exc}). Check your connection, or set {ENV_BIN_DIR}."
        ) from exc
    total = int(response.headers.get("Content-Length") or size or 0) or None
    digest = hashlib.sha256()
    done = 0
    part = dest.with_name(dest.name + ".part")
    with response, open(part, "wb") as out:
        while chunk := response.read(CHUNK):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if digest.hexdigest() != sha256:
        part.unlink(missing_ok=True)
        raise AssetError("the engine download failed its checksum. Try again.")
    os.replace(part, dest)


def _extract(archive: Path, dest: Path) -> None:
    """Extract a flat archive. Nested paths and traversal are rejected outright."""
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if "/" in name or "\\" in name or name in ("", ".", ".."):
                raise AssetError(f"unexpected path in engine archive: {name!r}")
            zf.extract(info, dest)


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > LOCK_STALE_S:
                    path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > deadline:
                raise AssetError("another Sweepr is installing the engine. Wait a moment and retry.")
            time.sleep(0.5)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def tool_version(tool: Path) -> str:
    """First line of `<tool> -version` (or `--version`), or a short error."""
    flag = "--version" if tool.name.startswith("deep-filter") else "-version"
    try:
        proc = subprocess.run(
            [str(tool), flag],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"error: {exc}"
    text = (proc.stdout or proc.stderr or "").strip().splitlines()
    return text[0] if text else f"exit {proc.returncode}"
