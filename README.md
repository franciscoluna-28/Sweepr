# DeepFilterNet Denoiser

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

- Windows with a Python 3.11 environment (already set up in `.venv`)

## Run

Double-click `run.bat`, or:

```
.venv\Scripts\python.exe start.py
```

Then open http://127.0.0.1:8765 (opened automatically).

## Reinstall dependencies

```
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

## Project layout

```
backend/    FastAPI app + DeepFilterNet engine
frontend/   Web UI (PWA)
start.py    Launcher (starts server, opens browser)
run.bat     Windows launcher
scripts/    Smoke test
```

## Notes

- The strength slider: 0 dB = no change, 100 dB = maximum suppression.
- Files are decoded and resampled to 48 kHz, processed, and returned as 16-bit WAV.
