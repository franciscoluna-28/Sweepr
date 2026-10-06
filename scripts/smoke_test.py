"""Proof-of-concept smoke test for the single-file denoiser.

Builds a synthetic 44.1 kHz noisy clip, runs it through the same code path the
API uses (`engine.enhance_bytes`), and asserts the output preserves the source
sample rate and is 24-bit. Run from the project root:

    .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""

import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import soundfile as sf

from app.engine import enhance_bytes

SR = 44100
DUR = 3.0
t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
rng = np.random.default_rng(0)
voice = 0.3 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
noise = 0.15 * rng.standard_normal(t.shape)
noisy = (voice + noise).astype(np.float32)

buf = io.BytesIO()
sf.write(buf, noisy, SR, format="WAV", subtype="PCM_16")
data = buf.getvalue()

for atten in (100, 12):
    t0 = time.time()
    out = enhance_bytes(data, "noisy.wav", atten, False)
    dt = time.time() - t0
    arr, sr = sf.read(io.BytesIO(out))
    info = sf.info(io.BytesIO(out))
    print(
        f"atten={atten:>3}dB  rtf={dt / DUR:.3f}  sr={sr}  "
        f"subtype={info.subtype}  out_rms={np.sqrt((arr**2).mean()):.5f}"
    )
    assert sr == SR, f"sample rate not preserved: {sr}"
    assert info.subtype == "PCM_24", f"not 24-bit: {info.subtype}"

print("input_rms=", np.sqrt((noisy**2).mean()))
print("OK")
