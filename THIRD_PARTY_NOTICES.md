# Third-party notices

Sweepr is distributed under the MIT License (see [`LICENSE`](LICENSE)). It
depends on and/or redistributes the following third-party components and
assets. This file is informational and does not modify those licenses.

## Runtime dependencies

| Component | Version | License | Source |
| --- | --- | --- | --- |
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | 0.5.6 | MIT OR Apache-2.0 | Rikorose/DeepFilterNet |
| [PyTorch](https://github.com/pytorch/pytorch) | 2.1.2 | BSD-3-Clause | pytorch/pytorch |
| [torchaudio](https://github.com/pytorch/audio) | 2.1.2 | BSD-2-Clause | pytorch/audio |
| [FastAPI](https://github.com/fastapi/fastapi) | 0.142.2 | MIT | fastapi/fastapi |
| [Uvicorn](https://github.com/encode/uvicorn) | 0.54.0 | BSD-3-Clause | encode/uvicorn |
| [Starlette](https://github.com/encode/starlette) | 1.7.0 | BSD-3-Clause | encode/starlette |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.13.5 | MIT | pydantic/pydantic |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.32 | Apache-2.0 | Kludex/python-multipart |
| [soundfile](https://github.com/bastibe/python-soundfile) | 0.14.0 | BSD-3-Clause | bastibe/python-soundfile |
| [NumPy](https://github.com/numpy/numpy) | 1.26.4 | BSD-3-Clause | numpy/numpy |
| [HTTPX](https://github.com/encode/httpx) | 0.28.1 | BSD-3-Clause | encode/httpx |

DeepFilterNet is dual-licensed under MIT OR Apache-2.0; Sweepr elects the MIT
option for its own distribution. Model weights are downloaded at runtime by
DeepFilterNet and are covered by that project's license.

## Front-end build dependencies

The UI (`app/ui/`) is built with Svelte, Vite, TypeScript, and Tailwind CSS,
each under its own license. These are build-time dependencies only and are not
redistributed with the app.

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
