# Sweepr

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Remove background noise from audio and video, locally, in your browser.
Powered by [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet). Your files
never leave the machine running Sweepr.

Sweepr is currently delivered as a **self-hosted Docker image** for a trusted
network. Desktop packages and one-line installers are in the source tree but are
not published yet.

## Self-hosting with Docker

Requirements: Docker with Compose, a 64-bit x86_64 host, and internet access for
the first build. ARM hosts need Docker amd64 emulation (slower); the bundled
engine is x86_64. The build downloads and checksum-verifies the engine; once the
image is built, Sweepr runs offline.

### 1. Configure

```sh
cp .env.example .env
```

Edit `.env`:

- `SWEEPR_TOKEN`: a long random value shared by everyone who uses the server.
  Generate one with `openssl rand -hex 24` (macOS/Linux) or
  `[guid]::NewGuid().ToString('N')` (PowerShell). If you leave it empty, Sweepr
  generates a new token on every start, so the link changes after a restart.
- `SWEEPR_HOST_PORT`: the port published on the server (default `8765`).
- `SWEEPR_BIND`: `127.0.0.1` keeps Sweepr on the server only. Set it to
  `0.0.0.0` (or a specific interface address) to reach it from another machine.
- `SWEEPR_TRUSTED_HOSTS`: the exact `Host` header values that may reach Sweepr,
  comma-separated. For LAN access include the published port, for example
  `192.168.1.50:8765`. Host matching is exact.

If only the server itself will use Sweepr, keep `SWEEPR_BIND=127.0.0.1` and
leave `SWEEPR_TRUSTED_HOSTS` empty.

### 2. Build and start

```sh
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml logs sweepr
```

The first build downloads the pinned engine (about 100 MB) and builds the UI.
Later starts are fast.

### 3. Open

- On the server: `http://127.0.0.1:8765/#token=<SWEEPR_TOKEN>`
- From another machine: `http://SERVER-IP:8765/#token=<SWEEPR_TOKEN>`

The token is the value you put in `.env`. If you changed `SWEEPR_HOST_PORT`, use
that published port in the URL. The log link inside the container uses the
internal port, so adjust it when you map a different host port.

The health check (`/api/health`) does not need a token; every other `/api` route
does.

Useful commands:

```sh
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec sweepr sweepr doctor
docker compose -f docker-compose.prod.yml down
```

Jobs live in the `sweepr-data` named volume and are pruned after 7 days.
`down -v` deletes the volume and all jobs.

### Reverse proxy and TLS

For a domain, keep `SWEEPR_BIND=127.0.0.1`, proxy to `127.0.0.1:8765`, and set
`SWEEPR_TRUSTED_HOSTS` to the `Host` header the proxy forwards. For a proxy on
port 443 that is usually the bare domain, e.g. `sweepr.example.com`; if the proxy
forwards a non-default port, include it. Terminate TLS at the proxy and do not
expose the container to the internet without TLS and access control.

### Troubleshooting

- **`400 invalid host header`**: add the exact host and port you use in the
  browser to `SWEEPR_TRUSTED_HOSTS` (for example `192.168.1.50:8765` or
  `sweepr.example.com`) and restart the container. If you changed
  `SWEEPR_HOST_PORT`, use that published port.
- **`401 missing or invalid access token`**: open the `#token=...` link. The
  token must match `SWEEPR_TOKEN`.
- **Health says `engine_ready: false`**: run `sweepr doctor` in the container
  (command above) and check the logs.
- **Port already in use**: change `SWEEPR_HOST_PORT` in `.env` and add the new
  `host:port` to `SWEEPR_TRUSTED_HOSTS` if clients use it directly.
- **ARM host**: the bundled engine is x86_64; use an x86_64 host.

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

Audio and video are processed on the machine running Sweepr. In Docker, jobs are
written to the `/data` volume (the `sweepr-data` named volume); finished jobs are
removed after 7 days. The engine is downloaded only while building the image, so
the running container makes no outbound requests.

When running from source, Sweepr uses the per-user data directory
(`%LOCALAPPDATA%\Sweepr` on Windows, `~/.local/share/sweepr` on Linux,
`~/Library/Application Support/Sweepr` on macOS).

## Engine and offline use

The image contains DeepFilterNet's `deep-filter`, LGPL `ffmpeg`/`ffprobe`, the
shared libraries, and the model. Build-time downloads are checked against the
SHA-256 pins in `sweepr_app/assets_manifest.json`. To build offline or use your
own Linux build, place the files in `engine-local/` (see that folder's README).

## Configuration

Docker Compose settings (`docker-compose.prod.yml`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `SWEEPR_TOKEN` | empty (random per start) | Fixed access token; set it for a stable link |
| `SWEEPR_HOST_PORT` | `8765` | Port published on the host |
| `SWEEPR_BIND` | `127.0.0.1` | Host interface; `0.0.0.0` for LAN access |
| `SWEEPR_TRUSTED_HOSTS` | empty | Exact allowed `Host` headers, comma-separated; include the port |

CLI settings (when running from source):

| Setting | Where | Meaning |
| --- | --- | --- |
| `--port`, `--host` | CLI | Listen address (default: `127.0.0.1`, port 8765 or a free port) |
| `--data-dir`, `SWEEPR_DATA_DIR` | CLI / env | Where jobs and logs are kept |
| `--token`, `SWEEPR_TOKEN` | CLI / env | Fixed access token (default: random per launch) |
| `--trusted-host`, `SWEEPR_TRUSTED_HOSTS` | CLI / env | Extra accepted `Host` names, comma-separated |
| `--no-browser` | CLI | Do not open a browser window |
| `SWEEPR_CACHE_DIR` | env | Where the downloaded engine is kept |
| `SWEEPR_BIN_DIR` | env | Use the engine from this folder (offline, development) |
| `SWEEPR_ASSET_BASE_URL` | env | Mirror for a published Sweepr engine archive |
| `SWEEPR_USE_SYSTEM_FFMPEG` | env | Force `ffmpeg`/`ffprobe` from `PATH` |

The access token is kept in memory only. Stopping Sweepr invalidates a random
token; set `SWEEPR_TOKEN` to keep the same link across restarts. Each launch is
an independent server, so a second launch picks the next free port instead of
reopening the first.

Processing limits are fixed product decisions, not settings: 10 files per batch,
5 GB per file, 10 GB per batch, 4 hours per file, 8 kHz to 192 kHz, mono or
stereo.

## Development

These requirements are only for running from source; the Docker image needs
none of them on the host. You need Python 3.11+ and [uv](https://docs.astral.sh/uv/),
Node 22 and pnpm 10 (for the UI), and a Rust toolchain only if you build the
engine yourself.

```sh
uv sync --extra dev
pnpm --dir sweepr_app/ui install
uv run python scripts/dev.py
```

That starts the backend and Vite together and opens
<http://127.0.0.1:5173/#token=dev>. On Windows you can also run
`.\scripts\dev.ps1`; on macOS/Linux, `sh scripts/dev.sh`.

Prefer two terminals? Run `uv run sweepr --no-browser --port 8765 --token dev`
and `pnpm --dir sweepr_app/ui dev` separately.

Run `uv run sweepr install-assets` once to fetch the pinned engine. On macOS,
also install `ffmpeg` with `brew install ffmpeg`. To use your own build, point
`SWEEPR_BIN_DIR` at a folder containing `deep-filter`, `ffmpeg`, and `ffprobe`.
`uv run sweepr doctor` reports what is missing.

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
.env.example           deployment settings template
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
