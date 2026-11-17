# Sweepr

[![PyPI](https://img.shields.io/pypi/v/sweepr-app.svg)](https://pypi.org/project/sweepr-app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Remove background noise from audio and video, locally, in your browser.
Powered by [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet). Your files
never leave your computer.

## Install and run

**Windows** (PowerShell):

```powershell
irm https://github.com/franciscoluna-28/sweepr/releases/latest/download/install.ps1 | iex
```

**macOS or Linux**:

```sh
curl -fsSL https://github.com/franciscoluna-28/sweepr/releases/latest/download/install.sh | sh
```

**Anywhere, if you already use uv or pipx**:

```sh
uvx --from sweepr-app sweepr
pipx install sweepr-app && sweepr
```

Sweepr opens in your browser. Drop in audio or video files, press **Clean my
audio**, and download the result. Keep the terminal window open while you use
it; Ctrl+C stops Sweepr.

The Windows installer adds a Start Menu shortcut and needs no admin rights. Use
`-NoShortcut`, `-NoLaunch`, or `-Uninstall` to change what it does.

### What the first run downloads

Sweepr downloads its engine once: the DeepFilterNet `deep-filter` program plus,
on Windows and Linux, `ffmpeg` and `ffprobe` (about 100 MB total). Every
download is checked against a SHA-256 checksum pinned in
`sweepr_app/assets_manifest.json`. macOS uses `deep-filter` from that download
and `ffmpeg` from `PATH` (`brew install ffmpeg`). Later runs start immediately
and work offline.

If something is missing, run `sweepr doctor`. It reports each component and what
to do about it.

## What it does

- **Audio or video in, cleaned audio out.** Videos come back with the cleaned
  audio muxed into the original picture; audio comes back as 24-bit WAV at the
  original sample rate.
- **Noise reduction strength** slider (0 = off, 100 = maximum), with an optional
  post-filter for very noisy sections.
- **Optional loudness evening** to -14 or -16 LUFS (EBU R128).
- **Quiet recordings** (typical of camera audio) are lifted before denoising so
  the model does not treat them as silence.
- **A/B compare**, per-file downloads, and a zip of everything in a batch.
- Batches of up to 10 files; files up to 5 GB and 4 hours long.

Supported inputs: WAV, MP3, FLAC, OGG, OPUS, MP4, MOV, MKV, WEBM, AVI, M4V.

## Privacy

Audio and video are processed on your machine and written to Sweepr's data
folder (`%LOCALAPPDATA%\Sweepr` on Windows, `~/.local/share/sweepr` on Linux,
`~/Library/Application Support/Sweepr` on macOS). Finished jobs are deleted after
7 days. Sweepr makes no network requests except the one-time engine download.

## Troubleshooting

Run `sweepr doctor`. Common fixes:

- **The engine is not installed:** start Sweepr once with internet access, or
  run `sweepr install-assets`. On macOS also install `ffmpeg` (`brew install
  ffmpeg`). Point `SWEEPR_BIN_DIR` at a folder with local binaries to stay
  offline.
- **Port 8765 is busy:** Sweepr picks a free port automatically and prints the
  address. Use `--port` to choose one.

## Self-hosting with Docker

Sweepr can run on a server or NAS for people on your network. Every request
except the health check must carry an access token.

```sh
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml logs sweepr
```

The logs print the link with a token generated at startup. To keep the same link
across restarts, set `SWEEPR_TOKEN` first:

```sh
export SWEEPR_TOKEN="$(openssl rand -hex 24)"
```

The port is published on `127.0.0.1` only. To reach it from other machines, set
`SWEEPR_BIND` to the interface address, and put a TLS reverse proxy in front of
it. Then add the proxy's host name to `SWEEPR_TRUSTED_HOSTS`.

The image bundles the engine, so it works offline once built. A fresh build
downloads the pinned engine automatically. Place Linux binaries in
`engine-local/` only to build offline or to use your own build (see that
folder's README).

## Configuration

| Setting | Where | Meaning |
| --- | --- | --- |
| `--port`, `--host` | CLI | Listen address (default: `127.0.0.1`, port 8765 or a free port) |
| `--data-dir`, `SWEEPR_DATA_DIR` | CLI / env | Where jobs and logs are kept |
| `--token`, `SWEEPR_TOKEN` | CLI / env | Fixed access token (default: random per launch) |
| `--trusted-host`, `SWEEPR_TRUSTED_HOSTS` | CLI / env | Extra accepted `Host` names, comma-separated (reverse proxies) |
| `--no-browser` | CLI | Do not open a browser window |
| `SWEEPR_CACHE_DIR` | env | Where the downloaded engine is kept |
| `SWEEPR_BIN_DIR` | env | Use the engine from this folder (offline, development) |
| `SWEEPR_ASSET_BASE_URL` | env | Mirror for a published Sweepr engine archive |
| `SWEEPR_USE_SYSTEM_FFMPEG` | env | Force `ffmpeg`/`ffprobe` from `PATH` |

The access token is generated when Sweepr starts and kept in memory only.
Stopping Sweepr invalidates the link; set `SWEEPR_TOKEN` (or `--token`) to keep a
fixed token across restarts. Each launch is an independent server, so a second
launch picks the next free port instead of reopening the first.

Processing limits are fixed product decisions, not settings: 10 files per batch,
5 GB per file, 10 GB per batch, 4 hours per file, 8 kHz to 192 kHz, mono or
stereo.

## Development

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/), Node 22 and
pnpm 10 (for the UI), and a Rust toolchain only if you build the engine yourself.

```sh
uv sync --extra dev                     # Python environment and test dependencies
pnpm --dir sweepr_app/ui install        # UI dependencies
uv run sweepr --no-browser --port 8765 --token dev   # backend (terminal 1)
pnpm --dir sweepr_app/ui dev            # UI with hot reload (terminal 2)
```

Open <http://127.0.0.1:5173/#token=dev>. Vite proxies `/api` to the backend.

Run `uv run sweepr install-assets` once to fetch the pinned engine. On macOS,
also install `ffmpeg` with `brew install ffmpeg`. To use your own build, point
`SWEEPR_BIN_DIR` at a folder containing `deep-filter`, `ffmpeg`, and `ffprobe`.

Run the checks:

```sh
uv run python scripts/smoke_test.py    # engine, API, security, CLI
pnpm --dir sweepr_app/ui check         # UI typecheck
pnpm --dir sweepr_app/ui build         # UI production build
```

## Project layout

```
sweepr_app/            The Python package (the `sweepr` command)
  cli.py               sweepr: start, doctor, install-assets
  server.py            FastAPI app factory: routes, upload guard, security
  security.py          Host allowlist, access token, security headers
  api.py               HTTP routes (validation and wiring)
  engine.py            ffmpeg + deep-filter pipeline
  jobs.py              job queue, manifests, cancellation
  assets.py            engine download, checksum verification, cache
  assets_manifest.json pinned engine components and archives per platform
  paths.py, limits.py  per-user directories, product limits
  ui/                  React + Vite + Tailwind frontend
scripts/               smoke test, engine and asset builds, installers, OpenAPI export
engine-local/          optional local engine binaries for Docker builds
Dockerfile             self-hosting image (UI build, package, engine)
docker-compose.prod.yml
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md). Commits
follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0).

## License

[MIT](LICENSE) © 2026 Francisco Luna. This covers Sweepr's own source code.
The engine and media tools are third-party components under their own licenses;
see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). The audio under
`demos/noisy/` is **not** MIT: it is third-party material relicensed under
SpeechBrain's Apache-2.0 terms, with per-file provenance in the same file.
