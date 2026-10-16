# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/franciscoluna-28/Sweepr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/franciscoluna-28/Sweepr/releases/tag/v0.1.0
