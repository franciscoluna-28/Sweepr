"""DeepFilterNet engine: header validation plus a file-to-file pipeline."""

import json
import os
import shutil
import subprocess
import tempfile
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import soundfile as sf
import torch
import torchaudio as ta
from df import enhance, init_df
from df.io import load_audio, resample

from . import limits

SR = 48000
_models = {}

# Quiet recordings (e.g. camera video) read as silence to the model, which then
# suppresses everything. Boost such inputs to a usable level; never attenuate.
TARGET_RMS_DB = -18.0
_PEAK_CEILING = 0.99

# Use every core; PyTorch is the only heavy user in this process.
torch.set_num_threads(os.cpu_count() or 1)


class AudioError(Exception):
    """A user-facing validation or decoding failure (message is safe to show)."""


def _is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in limits.VIDEO_EXTS


def _duration_limit_label() -> str:
    h, m = divmod(limits.MAX_DURATION_S // 60, 60)
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m} minutes")


def _ffmpeg(name: str = "ffmpeg") -> str:
    exe = shutil.which(name)
    if not exe:
        raise AudioError(
            f"video support requires {name}, which was not found on this machine"
        )
    return exe


def _probe_video(path: str) -> dict:
    """Validate a video's audio stream via ffprobe (no decode)."""
    ffprobe = _ffmpeg("ffprobe")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels:format=duration",
        "-of",
        "json",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout or "{}")
    except (OSError, ValueError):
        raise AudioError("could not read video file")
    streams = data.get("streams") or []
    if not streams:
        raise AudioError("contains no audio track")
    stream = streams[0]
    try:
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        duration = float((data.get("format") or {}).get("duration"))
    except (KeyError, TypeError, ValueError):
        raise AudioError("could not read the audio track")
    if sample_rate <= 0 or duration <= 0:
        raise AudioError("contains no audio data")
    if not limits.MIN_SAMPLE_RATE <= sample_rate <= limits.MAX_SAMPLE_RATE:
        raise AudioError(f"unsupported sample rate {sample_rate} Hz")
    if channels > limits.MAX_CHANNELS:
        raise AudioError(f"{channels} channels not supported (mono or stereo only)")
    if duration > limits.MAX_DURATION_S:
        raise AudioError(f"longer than {_duration_limit_label()}")
    return {
        "sample_rate": sample_rate,
        "num_frames": int(duration * sample_rate),
        "channels": channels,
        "duration": duration,
    }


def _extract_audio(src: str, tmp_dir: str) -> str:
    """Extract a video's audio track to a temporary WAV for the normal pipeline."""
    dst = os.path.join(tmp_dir, "audio.wav")
    cmd = [
        _ffmpeg(),
        "-y",
        "-nostdin",
        "-i",
        src,
        "-vn",
        "-map",
        "0:a:0",
        "-c:a",
        "pcm_s24le",
        dst,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError:
        raise AudioError("could not extract audio from video")
    if proc.returncode != 0 or not os.path.isfile(dst):
        raise AudioError("could not extract audio from video")
    return dst


def _level_input(audio):
    """Boost a quiet input toward TARGET_RMS_DB so the model has signal to work with."""
    rms = float(audio.pow(2).mean().sqrt())
    peak = float(audio.abs().max())
    if rms <= 1e-6 or peak <= 1e-6:
        return audio
    gain = 10.0 ** (TARGET_RMS_DB / 20.0) / rms
    gain = min(max(gain, 1.0), _PEAK_CEILING / peak)
    return audio * gain if gain != 1.0 else audio


def _get_model(post_filter: bool):
    if post_filter not in _models:
        model, df_state, suffix = init_df(
            post_filter=post_filter, log_file=None, log_level="ERROR"
        )
        _models[post_filter] = (model, df_state, suffix)
    return _models[post_filter]


def warmup():
    _get_model(False)
    _get_model(True)


def probe(path: str) -> dict:
    """Validate a file from its header alone (no decode). Raises AudioError.

    The extension allowlist lives in the API layer; this checks what the file
    actually *is*: decodable, sane sample rate/channels, within the duration
    cap. Header values can still lie, so process_file re-checks after decode.
    """
    if _is_video(path):
        return _probe_video(path)
    try:
        info = ta.info(path)
    except Exception:
        raise AudioError("not a decodable audio file")
    sample_rate = int(info.sample_rate)
    frames = int(info.num_frames)
    channels = int(info.num_channels)
    if sample_rate <= 0 or frames <= 0:
        raise AudioError("contains no audio data")
    if not limits.MIN_SAMPLE_RATE <= sample_rate <= limits.MAX_SAMPLE_RATE:
        raise AudioError(f"unsupported sample rate {sample_rate} Hz")
    if channels > limits.MAX_CHANNELS:
        raise AudioError(f"{channels} channels not supported (mono or stereo only)")
    duration = frames / sample_rate
    if duration > limits.MAX_DURATION_S:
        raise AudioError(f"longer than {limits.MAX_DURATION_S // 60} minutes")
    return {
        "sample_rate": sample_rate,
        "num_frames": frames,
        "channels": channels,
        "duration": duration,
    }


def process_file(src: str, dst: str, settings: dict) -> None:
    """Denoise one file into a 24-bit WAV, preserving the source sample rate."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        if _is_video(src):
            src = _extract_audio(src, tmp_dir)
        audio, info = load_audio(src, sr=SR)
    audio = _level_input(audio)
    src_sr = int(info.sample_rate)
    if audio.shape[-1] > limits.MAX_DURATION_S * SR:
        raise AudioError(f"longer than {_duration_limit_label()}")

    model, df_state, _ = _get_model(bool(settings["post_filter"]))
    with torch.inference_mode():
        out = enhance(
            model,
            df_state,
            audio,
            pad=True,
            atten_lim_db=float(settings["atten_lim_db"]),
        )
    out = out.to(torch.float32)

    if src_sr != SR:
        out = resample(out, SR, src_sr)
    samples = np.ascontiguousarray(out.numpy().T)
    np.clip(samples, -1.0, 1.0, out=samples)
    sf.write(dst, samples, src_sr, format="WAV", subtype="PCM_24")
