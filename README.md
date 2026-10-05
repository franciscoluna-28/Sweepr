# Meowless

A simple local web app for removing noise from audio using
[DeepFilterNet](https://github.com/Rikorose/DeepFilterNet). Everything runs on
your machine — recordings are never uploaded anywhere.

## Features

- Drag & drop an audio file and download the cleaned WAV
- **Noise reduction strength** slider (maps to DeepFilterNet's attenuation limit)
- Optional post-filter for extra suppression on very noisy parts
- A/B compare original vs enhanced
- Installable as a desktop app (PWA)

## Requirements

- Python 3.11 (already set up in `.venv`)
- Node.js + pnpm (build-time only — not needed to run the app)

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

## How the UI talks to the server

In production it's one process and one origin: FastAPI serves the built UI and
the `/api/*` routes, and the UI calls them with relative paths (`/api/...`).
There is no generated client — `app/ui/src/lib/api.ts` is a small hand-written
fetch wrapper. In dev the UI runs on Vite and proxies `/api` to the server.
Because the paths are relative, moving to a desktop shell (e.g. Tauri) later
needs no client changes.

## Project layout

```
app/             The monolith (one package, one process)
  main.py        Serves the built UI + handles /api/*
  engine.py      DeepFilterNet engine
  ui/            Svelte 5 + Vite + TypeScript + Tailwind source
  ui/dist/       Build output served by main.py
start.py         Launcher (starts server, opens browser)
run.bat          Windows launcher
scripts/         Smoke test
Dockerfile       Production image (UI build + Python runtime)
Dockerfile.dev   Dev API image
docker-compose.yml       Dev stack (api + web, HMR)
docker-compose.prod.yml  Production stack
```

## Notes

- The strength slider: 0 dB = no change, 100 dB = maximum suppression.
- Files are decoded and resampled to 48 kHz, processed, and returned as 16-bit WAV.
