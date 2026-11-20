"""TTS TIRUAN untuk uji alur tanpa jaringan: nada per kata dengan jeda di tanda baca.
Bukan suara manusia. Hanya untuk tes. Mengembalikan timestamps kata yang tepat."""
import re

import numpy as np

from .tts_gemini import pcm_ke_wav

RATE = 24000


def sintesis_tiruan(kata, keluar):
    """kata: list string. Return list {kata, mulai, selesai} yang tepat."""
    potongan, hasil, t = [], [], 0.2
    potongan.append(np.zeros(int(RATE * 0.2)))
    for k in kata:
        dur = 0.09 + 0.045 * len(re.sub(r"\W", "", k))
        n = int(RATE * dur)
        x = np.arange(n) / RATE
        frek = 170 + (sum(map(ord, k)) % 90)
        env = np.minimum(1, np.minimum(x / 0.02, (dur - x) / 0.03))
        potongan.append(0.35 * np.sin(2 * np.pi * frek * x) * env)
        hasil.append({"kata": k, "mulai": round(t, 3), "selesai": round(t + dur, 3)})
        jeda = 0.5 if k[-1:] in ".!?" else 0.22 if k[-1:] in ",;:" else 0.05
        potongan.append(np.zeros(int(RATE * jeda)))
        t += dur + jeda
    pcm = (np.concatenate(potongan) * 32767).astype("<i2").tobytes()
    pcm_ke_wav(pcm, RATE, keluar)
    return hasil
