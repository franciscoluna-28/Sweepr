# Migration: move all audio processing to a Rust sidecar

## Goal

Delegate **all audio processing** to a single native Rust binary
(`meowless-audio`). Python/FastAPI stops touching audio entirely and becomes a
thin API + static host. Svelte stays the frontend.

Focus for now: **realtime record mode** (mic → denoise → virtual cable). File
(Edit) mode is in scope for the end state but is a later phase.

## Why

The Python realtime path failed:

- **Underwater / low pitch** — we fed DeepFilterNet small blocks with stateless
  per-block normalization. DFN needs continuous STFT/feature/model state.
- **100% CPU + ~1 s delay** — upstream's adaptive latency deliberately inserts
  up to 1 s of delay when processing can't keep realtime (RTF ≥ 1). Torch
  per-hop on one CPU core hit that path.

DeepFilterNet already ships this exact thing in Rust (the LADSPA plugin and
PipeWire virtual mic). We port a proven design instead of inventing one.

## Target architecture

```
Svelte UI  ⇄  FastAPI (/api/*, serves UI, proxies record API)
                   ⇄ HTTP ⇄ meowless-audio.exe (Rust, native host process)
                                ⇄ WASAPI devices ⇄ VB-CABLE
```

- **FastAPI**: HTTP API, serves the built UI, proxies record endpoints to the
  sidecar. No audio code, no torch for realtime.
- **Rust sidecar**: device enumeration, capture, DeepFilterNet streaming,
  output to the virtual cable, meters, control.
- **Svelte**: unchanged; still talks to FastAPI.

The sidecar runs natively on the host because containers cannot reach Windows
audio (same reason the current Python bridge exists).

## Design (mirrors upstream LADSPA)

- Crate `deep_filter` (lib `df`), git-pinned, features
  `tract`, `default-model-ll` (DFN3 low-latency, no lookahead, 20 ms floor).
  Model is embedded via the feature — no runtime download.
- `cpal` for WASAPI capture/playback.
- Per session: input stream → ring buffer → worker thread calling
  `df.process()` one **480-sample hop** at a time → ring buffer → output stream.
- Live controls: attenuation limit, post-filter beta.
- RMS meters, RTF, and current latency reported via status.
- Keep upstream's adaptive-latency guard as a safety net, but tune so RTF ≪ 1
  and latency stays ~20–40 ms.

### Dependencies

```toml
deep_filter = { git = "https://github.com/Rikorose/DeepFilterNet", rev = "<pin>",
                default-features = false,
                features = ["tract", "default-model-ll", "transforms", "logging"] }
cpal = "0.15"
ndarray = "0.15"
axum = "0.7"
tokio = { version = "1", features = ["rt-multi-thread", "macros", "net"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
log = "0.4"
env_logger = "0.11"
```

`use-jemalloc` is non-Windows; skip it.

## Control contract (unchanged)

Keep the exact HTTP shape the current Python bridge exposes, so FastAPI's proxy
and the frontend need almost no changes.

- `GET /devices` → `{ inputs, outputs, virtual_cable, available, reason }`
- `GET /session/status` → `{ running, error, input_id, output_id,
  atten_lim_db, post_filter, block, latency_ms, input_rms, output_rms, drop }`
- `POST /session/start` → `{ input_id, output_id, input_name, output_name,
  atten_lim_db, post_filter, block }`
- `POST /session/stop`
- `PATCH /session` → live attenuation / post-filter / device swap

Device IDs drift when devices are plugged/unplugged, so the sidecar must resolve
devices by **name** at start time (preferring the WASAPI endpoint).

## Repo layout

```
audio/                      # new Rust crate
  Cargo.toml
  src/main.rs               # CLI + axum bootstrap
  src/devices.rs            # cpal enumeration, VB-CABLE detection, name resolution
  src/session.rs            # capture -> df.process -> output worker + ring buffers
  src/api.rs                # axum routes
```

## Phases

0. **Toolchain** — install rustup + MSVC Build Tools; verify `cargo build
   --release` on a hello-world.
1. **Spike (realtime)** — Rust CLI: select input/output, capture → `df.process`
   → CABLE, print RTF/latency. **Gate: RTF < 0.5, no adaptive delay, audio
   sounds clean.**
2. **Control API** — axum service matching the contract; verify `/devices` and
   start/stop.
3. **Cutover** — point FastAPI's record proxy at `meowless-audio.exe`; update
   `run.bat` / `run_docker.bat` to launch it; delete the Python realtime code
   (`app/virtualmic.py`, `app/bridge.py`, `audio_bridge.py`,
   `engine.StreamSession`).
4. **Edit mode** — move file denoising to Rust (the `deep-filter` library),
   then drop torch from the runtime.
5. **Docs + verify** — README, offline quality check (Rust vs Python on the
   smoke WAV), `pnpm check` / build unaffected.

## Risks

- tract RTF on this CPU is unmeasured → gate in phase 1; fall back to `ort`
  (ONNX Runtime) if it can't stay under realtime.
- MSVC Build Tools install is large/slow.
- The `_ll` model trades a little quality for zero lookahead; standard DFN3 can
  be exposed later.
- Pin a git **rev/tag** — crates.io `deep_filter` is stale (0.2.5).
