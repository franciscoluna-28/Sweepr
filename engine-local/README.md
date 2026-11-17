# Local engine (optional)

The Docker image downloads a pinned engine (DeepFilterNet's `deep-filter` plus
LGPL ffmpeg) and verifies every SHA-256 at build time. To build offline, or to
use your own build, place the Linux x86_64 binaries here before `docker build`:

- `deep-filter` (from `scripts/build_engine.py`)
- `ffmpeg` and `ffprobe` (LGPL builds; shared libraries next to them)

If `deep-filter` is present here, the download is skipped. This folder's
binaries are ignored by git.
