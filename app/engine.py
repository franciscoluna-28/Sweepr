import os
import tempfile
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import soundfile as sf
import torch
from libdf import DF, erb, erb_norm, unit_norm

from df import enhance, init_df
from df.enhance import get_device
from df.io import load_audio
from df.model import ModelParams
from df.utils import as_complex, as_real, get_norm_alpha

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


class StreamSession:
    """Low-latency, block-wise DeepFilterNet inference for live audio.

    Processes fixed blocks of `frames * hop` samples while keeping the
    STFT analysis/synthesis buffers continuous across calls. The model is
    stateless, so it is shared with the file-processing path.
    """

    def __init__(
        self, atten_lim_db: float = 100.0, post_filter: bool = False, frames: int = 2
    ):
        model, _, _ = _get_model(post_filter)
        p = ModelParams()
        self.model = model
        self.model.eval()
        self.df = DF(
            sr=p.sr,
            fft_size=p.fft_size,
            hop_size=p.hop_size,
            nb_bands=p.nb_erb,
            min_nb_erb_freqs=p.min_nb_freqs,
        )
        self.nb_df = p.nb_df
        self.hop = p.hop_size
        self.frames = max(2, frames)
        self.block = self.hop * self.frames
        self.alpha = get_norm_alpha(False)
        self.erb_fb = self.df.erb_widths()
        self.atten_lim_db = float(atten_lim_db)
        self.device = get_device()
        self.reset()

    def reset(self):
        self.df.reset()

    def set_atten(self, atten_lim_db: float):
        self.atten_lim_db = float(atten_lim_db)

    @torch.no_grad()
    def process(self, block: np.ndarray) -> np.ndarray:
        """Denoise one block of shape [C, T]. Returns [C, T] float32."""
        if block.ndim == 1:
            block = block[None, :]
        block = np.ascontiguousarray(block, dtype=np.float32)
        spec = self.df.analysis(block, reset=False)
        erb_feat = torch.as_tensor(
            erb_norm(erb(spec, self.erb_fb), self.alpha)
        ).unsqueeze(1)
        spec_feat = as_real(
            torch.as_tensor(unit_norm(spec[..., : self.nb_df], self.alpha)).unsqueeze(1)
        )
        spec2 = as_real(torch.as_tensor(spec).unsqueeze(1))
        dev = self.device
        enhanced = self.model(spec2.to(dev), erb_feat.to(dev), spec_feat.to(dev))[
            0
        ].cpu()
        enhanced = as_complex(enhanced.squeeze(1))
        if self.atten_lim_db > 0:
            lim = 10 ** (-abs(self.atten_lim_db) / 20)
            enhanced = as_complex(spec2.squeeze(1).cpu()) * lim + enhanced * (1 - lim)
        out = self.df.synthesis(enhanced.numpy(), reset=False)
        return np.asarray(out, dtype=np.float32)
