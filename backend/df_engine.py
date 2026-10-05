import os
import tempfile
import warnings

warnings.filterwarnings("ignore")

import soundfile as sf
import torch

from df import enhance, init_df
from df.io import load_audio

SR = 48000
_models = {}


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
    ext = os.path.splitext(filename)[1] or ".wav"
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        audio, _ = load_audio(path, sr=SR)
        model, df_state, _ = _get_model(post_filter)
        out = enhance(model, df_state, audio, pad=True, atten_lim_db=atten_lim_db)
        out = out.squeeze(0).numpy().T
        import io

        buf = io.BytesIO()
        sf.write(buf, out, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
