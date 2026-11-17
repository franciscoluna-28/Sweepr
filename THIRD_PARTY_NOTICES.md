# Third-party notices

Sweepr is distributed under the MIT License (see [`LICENSE`](LICENSE)). It
depends on and/or redistributes the following third-party components and
assets. This file is informational and does not modify those licenses.

## Runtime dependencies

The engine and media tools are downloaded by Sweepr on first run (or built by
our release pipeline) and verified against pinned SHA-256 checksums.

| Component | Version | License | Source |
| --- | --- | --- | --- |
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) (`deep-filter` CLI) | 0.5.6 (tag commit `978576aa`) | MIT OR Apache-2.0 | Rikorose/DeepFilterNet |
| [FFmpeg](https://ffmpeg.org) (`ffmpeg`, `ffprobe`) | 9.0 | LGPL-2.1-or-later (shared, no GPL components) | ffmpeg.org; LGPL build from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) |

DeepFilterNet is dual-licensed under MIT OR Apache-2.0; Sweepr elects the MIT
option for its own distribution. The DeepFilterNet3 model weights are compiled
into the `deep-filter` binary and are covered by that project's license.

FFmpeg is redistributed as shared libraries built without GPL components. The
license texts ship in the upstream ffmpeg archive. The corresponding source is
available from the FFmpeg project at the version above.

## Python runtime dependencies

| Component | License | Source |
| --- | --- | --- |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | fastapi/fastapi |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | encode/uvicorn |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | encode/starlette |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | pydantic/pydantic |
| [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 | Kludex/python-multipart |
| [platformdirs](https://github.com/tox-dev/platformdirs) | MIT | tox-dev/platformdirs |

Development-only test dependency: httpx2 (BSD-3-Clause).

## Front-end runtime dependencies

The UI is a React application built with Vite and Tailwind CSS.

| Component | License |
| --- | --- |
| [React](https://github.com/facebook/react) and React DOM | MIT |
| [Lucide](https://github.com/lucide-icons/lucide) (`lucide-react`) | ISC |
| [openapi-fetch](https://github.com/openapi-ts/openapi-typescript) | MIT |

Build-time only (not redistributed): Vite, Tailwind CSS, TypeScript,
openapi-typescript, and the React plugin for Vite, each under its own license.

## Bundled media assets

The files under `demos/noisy/` are **not** covered by Sweepr's MIT license (see
[`LICENSE`](LICENSE)). They are third-party recordings redistributed here for
manual testing and evaluation, under the Apache-2.0 license of the SpeechBrain
project. The `NN_<project>_<name>` filenames are Sweepr's own labels.

| File | Upstream source (exact path) | Upstream license |
| --- | --- | --- |
| `08_speechbrain_singlemic1.wav` | `speechbrain/speechbrain` → `tests/samples/single-mic/example1.wav` | Apache-2.0 |
| `09_speechbrain_singlemic5.wav` | `speechbrain/speechbrain` → `tests/samples/single-mic/example5.wav` | Apache-2.0 |
| `10_speechbrain_addnoise.flac` | Derivative of `speechbrain/speechbrain` → `tests/samples/single-mic/example1.wav` + added noise (re-encoded with FFmpeg 6.0) | Apache-2.0 |

Each file was confirmed byte-for-byte (SHA-256) against its upstream source
(`10_speechbrain_addnoise.flac` matches the duration of `example1.wav` and is an
FFmpeg 6.0 re-encode, i.e. a noisy derivative rather than a stock upstream file).

The NonCommercial demo samples that were previously in this directory (from
`Rikorose/DeepFilterNet` and `facebookresearch/denoiser`) have been removed, so
the repository ships no NonCommercial media. Do not reintroduce them unless you
accept the NonCommercial terms.
