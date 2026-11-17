"""Assemble one engine archive per platform and pin its checksum in the manifest.

Each archive is flat and contains exactly what Sweepr needs at runtime:

    deep-filter(.exe)  ffmpeg(.exe)  ffprobe(.exe)  <shared libraries>  LICENSE-*

Windows and Linux ffmpeg come from pinned BtbN LGPL *shared* builds (checksums
below, verified before use). macOS has no pinned upstream build here; build
ffmpeg from source in CI and pass its folder with --ffmpeg-dir.

    uv run python scripts/build_assets.py --platform windows-x86_64 \
        --deep-filter dist/engine/deep-filter.exe --update-manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "sweepr_app" / "assets_manifest.json"
FFMPEG_RELEASE = "autobuild-2026-11-15-12-40"
BTBN = f"https://github.com/BtbN/FFmpeg-Builds/releases/download/{FFMPEG_RELEASE}"

# Pinned upstream archives. Checksums come from the GitHub release digests.
PINNED_FFMPEG = {
    "windows-x86_64": {
        "url": f"{BTBN}/ffmpeg-n9.0.2-57-gd838f9f9ae-win64-lgpl-shared-9.0.zip",
        "sha256": "6305750bb1b4e3f80d17a6644fec1cf57eef12106c4f9192ddb05e14a6b522b0",
        "kind": "zip",
    },
    "linux-x86_64": {
        "url": f"{BTBN}/ffmpeg-n9.0.2-57-gd838f9f9ae-linux64-lgpl-shared-9.0.tar.xz",
        "sha256": "91cc21d810b82d391a78c1bdf60a60922f56b91a69589e11e76a5195f343a81d",
        "kind": "tar",
    },
}

EXE_SUFFIX = {"windows-x86_64": ".exe"}
LIB_SUFFIXES = (".dll", ".so", ".dylib")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_verified(url: str, expected: str, dest: Path) -> Path:
    print(f"fetching {url.rsplit('/', 1)[-1]}")
    with urllib.request.urlopen(url, timeout=600) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    actual = sha256_of(dest)
    if actual != expected:
        raise SystemExit(f"checksum mismatch for {url}: expected {expected}, got {actual}")
    return dest


def extract_pinned(platform: str, workdir: Path) -> Path:
    spec = PINNED_FFMPEG[platform]
    archive = fetch_verified(spec["url"], spec["sha256"], workdir / Path(spec["url"]).name)
    root = workdir / "ffmpeg-extract"
    root.mkdir()
    if spec["kind"] == "zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(root)
    else:
        with tarfile.open(archive) as tf:
            tf.extractall(root, filter="data")
    # The archive has one top-level folder; its bin/ (Windows) or bin+lib (Linux) hold the payload.
    top = next(p for p in root.iterdir() if p.is_dir())
    return top


def gather_ffmpeg(source: Path, platform: str) -> tuple[list[Path], list[Path]]:
    """Return (executables, shared libraries) from an ffmpeg build tree."""
    suffix = EXE_SUFFIX.get(platform, "")
    bin_dirs = [p for p in (source / "bin", source / "lib", source) if p.is_dir()]

    def find(name: str) -> Path:
        for directory in bin_dirs:
            candidate = directory / f"{name}{suffix}"
            if candidate.is_file():
                return candidate
        raise SystemExit(f"{name}{suffix} not found under {source}")

    executables = [find("ffmpeg"), find("ffprobe")]
    libs = [
        p
        for d in bin_dirs
        for p in d.iterdir()
        if p.is_file() and not p.is_symlink() and any(s in p.name for s in LIB_SUFFIXES) and p not in executables
    ]
    return executables, sorted(set(libs))


def licenses_from(source: Path) -> list[tuple[Path, str]]:
    found = [p for p in source.iterdir() if p.is_file() and p.name.upper().startswith(("LICENSE", "COPYING"))]
    return [(p, f"LICENSE-ffmpeg-{p.name}") for p in sorted(found)]


def build_archive(platform: str, deep_filter: Path, ffmpeg_dir: Path | None, version: str, out_dir: Path) -> Path:
    suffix = EXE_SUFFIX.get(platform, "")
    with tempfile.TemporaryDirectory(prefix="sweepr-assets-") as tmp:
        work = Path(tmp)
        if ffmpeg_dir is None:
            if platform not in PINNED_FFMPEG:
                raise SystemExit(f"{platform} needs --ffmpeg-dir (no pinned upstream build)")
            ffmpeg_dir = extract_pinned(platform, work)
        executables, libs = gather_ffmpeg(ffmpeg_dir, platform)

        staging = work / "stage"
        staging.mkdir()
        shutil.copy2(deep_filter, staging / f"deep-filter{suffix}")
        for exe in executables:
            shutil.copy2(exe, staging / exe.name)
        for lib in libs:
            shutil.copy2(lib, staging / lib.name)

        licences = [
            (ROOT / "LICENSE", "LICENSE-sweepr.txt"),
            (ROOT / "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
            (deep_filter.parent / "LICENSE-deep-filter-MIT.txt", "LICENSE-deep-filter-MIT.txt"),
            (deep_filter.parent / "LICENSE-deep-filter-APACHE.txt", "LICENSE-deep-filter-APACHE.txt"),
        ]
        licences += licenses_from(ffmpeg_dir)
        for src, name in licences:
            if src.is_file():
                shutil.copy2(src, staging / name)

        out_dir.mkdir(parents=True, exist_ok=True)
        archive = out_dir / f"sweepr-assets-{version}-{platform}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(staging.iterdir()):
                zf.write(item, arcname=item.name)
    return archive


def update_manifest(platform: str, archive: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = manifest["platforms"][platform]
    if entry["file"] != archive.name:
        raise SystemExit(f"manifest expects {entry['file']}, built {archive.name}")
    entry["sha256"] = sha256_of(archive)
    entry["size"] = archive.stat().st_size
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifest updated: sha256={entry['sha256'][:12]}... size={entry['size']}")


def verify_manifest(platform: str, archive: Path) -> None:
    """Fail unless the archive matches the checksum pinned in the manifest."""
    entry = json.loads(MANIFEST.read_text(encoding="utf-8"))["platforms"][platform]
    if entry["file"] != archive.name:
        raise SystemExit(f"manifest expects {entry['file']}, got {archive.name}")
    actual = sha256_of(archive)
    if entry["sha256"] != actual:
        raise SystemExit(
            f"manifest checksum for {platform} is {entry['sha256']}, archive is {actual}. "
            "Update scripts/build_assets.py --update-manifest in a reviewed commit."
        )
    print(f"verified {archive.name} matches the manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--platform", required=True, choices=sorted(json.loads(MANIFEST.read_text())["platforms"]))
    parser.add_argument("--deep-filter", type=Path, help="built deep-filter executable")
    parser.add_argument("--ffmpeg-dir", type=Path, help="ffmpeg build tree (required for macOS)")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "assets")
    parser.add_argument("--update-manifest", action="store_true", help="write checksum and size into the manifest")
    parser.add_argument("--verify", type=Path, metavar="ARCHIVE", help="check an existing archive against the manifest")
    args = parser.parse_args()

    if args.verify:
        verify_manifest(args.platform, args.verify.resolve())
        return
    if args.deep_filter is None:
        parser.error("--deep-filter is required to build an archive")

    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    archive = build_archive(args.platform, args.deep_filter.resolve(), args.ffmpeg_dir, version, args.out.resolve())
    print(f"built {archive} ({archive.stat().st_size / 1e6:.1f} MB)")
    if args.update_manifest:
        update_manifest(args.platform, archive)


if __name__ == "__main__":
    main()
