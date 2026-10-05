import time

import numpy as np
import soundfile as sf
import torch

from df import enhance, init_df

SR = 48000
t = np.linspace(0, 3.0, int(SR * 3.0), endpoint=False)
rng = np.random.default_rng(0)
voice = 0.3 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
noise = 0.15 * rng.standard_normal(t.shape)
noisy = (voice + noise).astype(np.float32)

sf.write("noisy.wav", noisy, SR)
audio = torch.from_numpy(noisy).unsqueeze(0)

t0 = time.time()
model, df_state, suffix = init_df(log_file=None, log_level="ERROR")
print(f"model loaded in {time.time() - t0:.2f}s -> {suffix}")

for atten in (100, 12):
    t0 = time.time()
    out = enhance(model, df_state, audio, atten_lim_db=atten)
    dt = time.time() - t0
    arr = out.squeeze(0).numpy()
    sf.write(f"enhanced_{atten}.wav", arr, SR)
    print(
        f"atten={atten:>3}dB  rtf={dt / 3.0:.3f}  out_rms={np.sqrt((arr**2).mean()):.5f}"
    )

print("input_rms=", np.sqrt((noisy**2).mean()))
print("OK")
