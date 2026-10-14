# Sweepr

A simple local web app for removing noise from a single audio file using
[DeepFilterNet](https://github.com/Rikorose/DeepFilterNet). Everything runs on
your machine — recordings are never uploaded anywhere.

## Features

- **Denoise one audio file** — drag & drop, or browse, and download the cleaned
  WAV
- **Video input** — drop an `mp4`, `mov`, `mkv`, `webm`, `avi`, or `m4v` and get
  the video back with the cleaned audio muxed in (video stream copied, audio
  re-encoded). The enhanced audio track is still available as WAV
- **Noise reduction strength** slider (maps to DeepFilterNet's attenuation limit)
- Optional post-filter for extra suppression on very noisy parts
- Optional loudness normalization after cleaning (target -14 or -16 LUFS, with
  a -1 dBTP true-peak ceiling; off by default, requires `ffmpeg`)
- A/B compare original vs enhanced
- Preserves the original sample rate; output is 24-bit WAV

## Requirements

- Python 3.11 (already set up in `.venv`)
- Node.js + pnpm (build-time only — not needed to run the app)
- `ffmpeg` on your `PATH` (required only for video input)

## Setup

```
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
pnpm --dir app/ui install
```

## Run

The app is a single Python process: it serves the built UI and handles requests.

```
pnpm --dir app/ui build
.venv\Scripts\python.exe start.py
```

Or just double-click `run.bat` (builds if needed, then starts). Open
http://127.0.0.1:8765 (opens automatically).

## Development

Run the server and the Vite dev server (with HMR) side by side:

```
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8765
pnpm --dir app/ui dev
```

Vite proxies `/api` to the Python process. Node is used for building only; the
production app runs entirely on Python.

## Docker

### Dev (hot reload)

```
docker compose up --build
```

- UI with HMR: http://localhost:5173 (Vite proxies `/api` to the `api` service)
- API + docs: http://localhost:8765/docs

Source (`app/`) is bind-mounted, so Python auto-reloads (`uvicorn --reload`) and
the UI hot-reloads (Vite). The model cache and `node_modules` live in named
volumes.

### Production

```
docker compose -f docker-compose.prod.yml up --build
```

Builds the UI in a Node stage, then serves it (plus the API) from one Python
container on http://localhost:8765.

## Configuration

Limits are enforced server-side and mirrored to the UI via `/api/health`. Every
value below can be overridden with an environment variable; invalid values make
the app fail fast at startup with a message naming the variable.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SWEEPR_MAX_FILES` | `10` | Files per batch job |
| `SWEEPR_MAX_FILE_BYTES` | `5G` | Per-file size cap |
| `SWEEPR_MAX_TOTAL_BYTES` | `10G` | Per-job total upload cap (≥ per-file cap) |
| `SWEEPR_MAX_DURATION_S` | `14400` | Max media duration in seconds |
| `SWEEPR_MAX_WAITING_JOBS` | `3` | Jobs allowed to wait in the queue |
| `SWEEPR_RETENTION_DAYS` | `7` | Days before finished jobs are pruned |
| `SWEEPR_JOBS_DIR` | `app/data/jobs` | Job storage dir (point at a mounted volume in the cloud) |
| `SWEEPR_PORT` | `8765` | HTTP port (falls back to platform `PORT`, e.g. Cloud Run / Fly) |

Byte sizes accept plain integers (bytes) or human suffixes: `5120M`, `5G`, `5GiB`.

Format allowlists (extensions, sample rates, channels) are intentionally not
configurable.

Example (docker compose reads `SWEEPR_PORT` from your shell or `.env`):

```
SWEEPR_PORT=9000 SWEEPR_MAX_FILES=2 docker compose -f docker-compose.prod.yml up --build
```

## How the UI talks to the server

In production it's one process and one origin: FastAPI serves the built UI and
the `/api/*` routes, and the UI calls them with relative paths (`/api/...`).
In dev the UI runs on Vite and proxies `/api` to the server. Because the paths
are relative, moving to a desktop shell (e.g. Tauri) later needs no client
changes.

The client is typed from the API itself. FastAPI's OpenAPI schema is exported to
`app/ui/openapi.json`, then `openapi-typescript` generates
`app/ui/src/lib/api-schema.d.ts`. The thin `app/ui/src/lib/api.ts` wraps the
generated types with the tiny `openapi-fetch` client, plus a few domain helpers
(job polling, direct file/zip URLs) that codegen can't express. After changing a
route or a model in `app/schemas.py`, regenerate:

```
.venv\Scripts\python.exe scripts\export_openapi.py
pnpm --dir app/ui gen:api
```

The generated files are committed, so the UI's Node-only build stage (and CI)
don't need Python.

## Project layout

```
app/             The monolith (one package, one process)
  main.py        Serves the built UI + handles /api/* (standard error shape)
  api.py         HTTP routes (validation + wiring, no DSP)
  schemas.py     Pydantic response/error models (source of the OpenAPI schema)
  engine.py      DeepFilterNet engine (single-file, sample-rate preserving)
  ui/            Svelte 5 + Vite + TypeScript + Tailwind source
    openapi.json          Exported FastAPI schema (generated)
    src/lib/api-schema.d.ts  Generated types (committed)
  ui/dist/       Build output served by main.py
start.py         Launcher (starts server, opens browser)
run.bat          Windows launcher
scripts/         Smoke test + OpenAPI exporter
Dockerfile       Production image (UI build + Python runtime)
Dockerfile.dev   Dev API image
docker-compose.yml       Dev stack (api + web, HMR)
docker-compose.prod.yml  Production stack
```

## Notes

- The strength slider: 0 dB = no change, 100 dB = maximum suppression.
- Very quiet recordings (common in camera/video audio) are automatically boosted
  to a usable level before denoising — otherwise the model treats them as
  silence. Loud inputs are left untouched.
- DeepFilterNet processes at 48 kHz internally; Sweepr resamples back to the
  source rate and writes a 24-bit WAV.
- Loudness normalization runs *after* denoising (and before muxing a video), so
  the cleaned audio is measured once and brought to target with a single linear
  gain. It changes level, not signal-to-noise — only the denoiser does that.
