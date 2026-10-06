"""DeepFilterNet engine: header validation plus a file-to-file pipeline."""

import os
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

# Use every core; PyTorch is the only heavy user in this process.
torch.set_num_threads(os.cpu_count() or 1)


class AudioError(Exception):
    """A user-facing validation or decoding failure (message is safe to show)."""


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
    return {"sample_rate": sample_rate, "num_frames": frames, "channels": channels, "duration": duration}


def process_file(src: str, dst: str, settings: dict) -> None:
    """Denoise one file into a 24-bit WAV, preserving the source sample rate."""
    audio, info = load_audio(src, sr=SR)
    src_sr = int(info.sample_rate)
    if audio.shape[-1] > limits.MAX_DURATION_S * SR:
        raise AudioError(f"longer than {limits.MAX_DURATION_S // 60} minutes")

    model, df_state, _ = _get_model(bool(settings["post_filter"]))
    with torch.inference_mode():
        out = enhance(
            model, df_state, audio, pad=True, atten_lim_db=float(settings["atten_lim_db"])
        )
    out = out.to(torch.float32)

    if src_sr != SR:
        out = resample(out, SR, src_sr)
    samples = np.ascontiguousarray(out.numpy().T)
    np.clip(samples, -1.0, 1.0, out=samples)
    sf.write(dst, samples, src_sr, format="WAV", subtype="PCM_24")
