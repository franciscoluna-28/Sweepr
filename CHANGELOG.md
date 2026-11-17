# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]

First public release, distributed as a Python package and as an installer
script. Sweepr runs in your browser and works offline after the first run.

### Added

- `uvx --from sweepr-app sweepr`, `pipx install sweepr-app`, and one-line
  installers for Windows (`install.ps1`) and macOS/Linux (`install.sh`).
- The engine (DeepFilterNet's `deep-filter` plus LGPL ffmpeg) is downloaded on
  first run and checked against pinned SHA-256 checksums. `sweepr doctor` reports
  its status.
- Per-launch access token, loopback binding, Host-header allowlist, and a strict
  Content-Security-Policy for the local server. Docker generates a token at
  startup; set `SWEEPR_TOKEN` to keep one across restarts. Empty tokens are
  refused at startup.
- Docker image for self-hosting, with the engine and its shared libraries
  bundled.

### Changed

- The UI is now React with Vite (it was Svelte).
- The app is packaged as `sweepr-app` with the `sweepr` command; the Python
  package is `sweepr_app`.
- Job and cache storage moved to per-user platform directories. Settings that
  were environment-driven limits are now fixed product limits.
- Denoising uses the `deep-filter` CLI rather than PyTorch; the same
  DeepFilterNet3 model runs in a much smaller install.
- The access token is kept in memory only. Sweepr no longer writes a per-launch
  `instance.json` state file, and a second launch starts an independent server
  instead of reopening the first.
- Engine downloads use pinned upstream DeepFilterNet `deep-filter` binaries and
  pinned BtbN ffmpeg archives when no Sweepr engine archive is published. Fresh
  clones and Docker builds no longer require `engine-local/`; it remains an
  optional offline override.

### Removed

- PyTorch, torchaudio, deepfilternet, soundfile, numpy, and the `.env` / run-script
  launchers.
- GitHub Actions CI/CD workflows; run the documented checks locally for now.

## [0.1.0] - 2026-10-16

Initial public release.

### Added

- Local web app that removes background noise from audio using DeepFilterNet,
  with a drag-and-drop Svelte UI served by the same FastAPI process.
- Single-file and batch jobs with an on-disk job queue and worker thread.
- Video input: cleaned audio is muxed back into the original video stream.
- Noise reduction strength slider, optional post-filter, and optional EBU R128
  loudness normalization.
- A/B compare and per-file / zip downloads.
- Server-side limits configurable via `SWEEPR_*` environment variables.
- Docker dev and production stacks, an end-to-end smoke test, and generated,
  committed OpenAPI/TypeScript API artifacts.

[1.0.0]: https://github.com/franciscoluna-28/Sweepr/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/franciscoluna-28/Sweepr/releases/tag/v0.1.0
