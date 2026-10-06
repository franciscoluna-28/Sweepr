"""EBU R128 loudness normalization (applied after denoising)."""

import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly

PEAK_CEILING_DBTP = -1.0
_PEAK_CEILING = 10 ** (PEAK_CEILING_DBTP / 20.0)


def _loudness(data: np.ndarray, sr: int) -> float:
    try:
        value = float(pyln.Meter(sr).integrated_loudness(data.astype(np.float64)))
    except Exception:
        return float("nan")
    return value


def normalize(samples: np.ndarray, sr: int, target_lufs: float) -> tuple[np.ndarray, float, float]:
    """Scale to target integrated loudness with a true-peak ceiling.

    ``samples`` is a float array shaped (frames,) or (frames, channels) in
    [-1, 1]. Returns ``(samples, lufs_before, lufs_after)``; loudness values
    are NaN when the signal is silent or too short to measure.
    """
    was_mono = samples.ndim == 1
    data = samples.reshape(-1, 1) if was_mono else samples

    before = _loudness(data, sr)
    if not np.isfinite(before):
        return samples, before, float("nan")

    gain = 10.0 ** ((target_lufs - before) / 20.0)
    scaled = data * gain

    # True peak via 4x oversampling; headroom wins over the target.
    peak = float(np.max(np.abs(resample_poly(scaled.astype(np.float64), 4, 1, axis=0))))
    if peak > _PEAK_CEILING:
        scaled = scaled * (_PEAK_CEILING / peak)

    after = _loudness(scaled, sr)
    return (scaled.reshape(-1) if was_mono else scaled), before, after
