"""Detectores de DTMF e CTCSS (sub-tom) baseados no algoritmo de Goertzel."""
from __future__ import annotations

import numpy as np

from ..dsp.filters import Decimator

CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4, 100.0,
    103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8, 136.5, 141.3, 146.2,
    150.0, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9, 171.3, 173.8, 177.3, 179.9,
    183.5, 186.2, 189.9, 192.8, 196.6, 199.5, 203.5, 206.5, 210.7, 218.1, 225.7,
    229.1, 233.6, 241.8, 250.3, 254.1,
]

DTMF_LOW = [697, 770, 852, 941]
DTMF_HIGH = [1209, 1336, 1477, 1633]
DTMF_KEYS = ["123A", "456B", "789C", "*0#D"]


_KERNELS: dict = {}


def goertzel_power(x: np.ndarray, freqs, fs: float) -> np.ndarray:
    """Potência em várias frequências (vetorizado via produto com exponenciais)."""
    key = (len(x), tuple(freqs), fs)
    e = _KERNELS.get(key)
    if e is None:
        n = np.arange(len(x))
        f = np.asarray(freqs, dtype=np.float64)[:, None]
        e = np.exp(-2j * np.pi * f * n / fs)
        if len(_KERNELS) > 16:
            _KERNELS.clear()
        _KERNELS[key] = e
    return np.abs(e @ x) ** 2 / max(len(x), 1) ** 2


class DTMFDecoder:
    RATE = 8000
    FRAME = 205  # ~25.6 ms

    def __init__(self, on_digit, input_rate: int = 48_000):
        self.on_digit = on_digit
        self.dec = Decimator(input_rate // self.RATE, cutoff=0.9)
        self._buf = np.zeros(0, np.float32)
        self._last = None
        self._count = 0
        self._emitted = False

    def process(self, audio: np.ndarray):
        self._buf = np.concatenate((self._buf, self.dec.process(audio)))
        while len(self._buf) >= self.FRAME:
            fr = self._buf[:self.FRAME].astype(np.float64)
            self._buf = self._buf[self.FRAME:]
            self._frame(fr)

    def _frame(self, x):
        total = np.mean(x ** 2) + 1e-12
        lo = goertzel_power(x, DTMF_LOW, self.RATE)
        hi = goertzel_power(x, DTMF_HIGH, self.RATE)
        il, ih = int(np.argmax(lo)), int(np.argmax(hi))
        key = None
        # cada tom senoidal de amplitude A tem potência ~A²/4 aqui; energia total ~ (A1²+A2²)/2
        if (lo[il] + hi[ih]) * 2 > 0.6 * total:
            lo_s, hi_s = np.sort(lo), np.sort(hi)
            if lo_s[-2] < 0.15 * lo[il] and hi_s[-2] < 0.15 * hi[ih]:
                twist = 10 * np.log10((hi[ih] + 1e-15) / (lo[il] + 1e-15))
                if -8 < twist < 8:
                    key = DTMF_KEYS[il][ih]
        if key is not None and key == self._last:
            self._count += 1
            if self._count >= 2 and not self._emitted:
                self.on_digit(key)
                self._emitted = True
        else:
            self._count = 1 if key else 0
            self._emitted = False
        self._last = key


class CTCSSDetector:
    """Detecta sub-tom CTCSS em janelas de 1 s (resolução ~1 Hz)."""

    RATE = 1000

    def __init__(self, input_rate: int = 48_000, window_s: float = 1.0):
        self.dec1 = Decimator(8, cutoff=0.9)       # 48k -> 6k
        self.dec2 = Decimator(6, cutoff=0.5)       # 6k -> 1k (passa-baixa ~250 Hz)
        self.win = int(self.RATE * window_s)
        self._buf = np.zeros(0, np.float32)
        self.tone: float | None = None
        self.level = 0.0

    def process(self, audio: np.ndarray) -> float | None:
        x = self.dec2.process(self.dec1.process(audio))
        self._buf = np.concatenate((self._buf, x))[-self.win:]
        if len(self._buf) < self.win:
            return self.tone
        seg = self._buf - np.mean(self._buf)
        seg = seg * np.hanning(len(seg))
        p = goertzel_power(seg, CTCSS_TONES, self.RATE)
        i = int(np.argmax(p))
        others = np.delete(p, [j for j in (i - 1, i, i + 1) if 0 <= j < len(p)])
        ref = np.median(others) + 1e-15
        self.level = float(10 * np.log10(p[i] / ref))
        total = np.mean(seg ** 2) + 1e-15
        if self.level > 15 and p[i] / total > 0.02:
            self.tone = CTCSS_TONES[i]
        else:
            self.tone = None
        return self.tone
