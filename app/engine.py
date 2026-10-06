import io
import os
import tempfile
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import soundfile as sf
import torch
from df import enhance, init_df
from df.enhance import get_device
from df.io import load_audio, resample

SR = 48000
_models = {}

# Use every core; PyTorch is the only heavy user in this process.
torch.set_num_threads(os.cpu_count() or 1)


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


def enhance_bytes(
    data: bytes, filename: str, atten_lim_db: float, post_filter: bool
) -> bytes:
    """Denoise one audio file, preserving its sample rate, as 24-bit WAV."""
    ext = os.path.splitext(filename)[1] or ".wav"
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        audio, info = load_audio(path, sr=SR)
        model, df_state, _ = _get_model(post_filter)
        with torch.inference_mode():
            out = enhance(model, df_state, audio, pad=True, atten_lim_db=atten_lim_db)
        out = out.to(torch.float32)
        src_sr = int(info.sample_rate)
        if src_sr != SR:
            out = resample(out, SR, src_sr)
        samples = np.clip(out.squeeze(0).numpy().T, -1.0, 1.0)
        buf = io.BytesIO()
        sf.write(buf, samples, src_sr, format="WAV", subtype="PCM_24")
        return buf.getvalue()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
