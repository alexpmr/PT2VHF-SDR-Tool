"""Processamento de áudio: equalizador, redução de ruído, notch, filtros de tom."""
from __future__ import annotations

import numpy as np
from scipy import signal

from .filters import SOSFilter

EQ_BANDS_HZ = [100, 200, 400, 800, 1600, 3200, 6400, 12000]

EQ_PRESETS = {
    "Plano": [0, 0, 0, 0, 0, 0, 0, 0],
    "Voz (SSB/FM)": [-12, -6, 0, 3, 4, 3, -3, -12],
    "Voz clara": [-6, -3, 0, 2, 4, 5, 2, -6],
    "Graves": [6, 4, 2, 0, 0, 0, 0, 0],
    "Música (WFM)": [4, 2, 0, -1, 0, 1, 3, 4],
    "Telefonia": [-20, -10, 0, 0, 2, 0, -10, -20],
}


def peaking_sos(fs: float, f0: float, gain_db: float, q: float = 1.1) -> np.ndarray:
    """Biquad 'peaking EQ' (RBJ cookbook) como uma seção SOS."""
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2 * q)
    b = np.array([1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a])
    aa = np.array([1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a])
    return np.concatenate((b / aa[0], aa / aa[0]))[None, :]


class Equalizer:
    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate
        self.enabled = False
        self.gains = [0.0] * len(EQ_BANDS_HZ)
        self._filter: SOSFilter | None = None
        self._rebuild()

    def set_gains(self, gains):
        self.gains = [float(g) for g in gains]
        self._rebuild()

    def _rebuild(self):
        secs = [peaking_sos(self.sample_rate, f, g)
                for f, g in zip(EQ_BANDS_HZ, self.gains)
                if abs(g) > 0.05 and f < self.sample_rate / 2.2]
        self._filter = SOSFilter(np.vstack(secs)) if secs else None

    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled or self._filter is None:
            return x
        return self._filter.process(x)


class Notch:
    """Filtro notch manual (remove portadora/heteródino)."""

    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate
        self.enabled = False
        self.freq = 1000.0
        self.q = 15.0
        self._f = None
        self._build()

    def set_freq(self, f: float):
        self.freq = float(f)
        self._build()

    def _build(self):
        f = min(max(self.freq, 20.0), self.sample_rate / 2.2)
        b, a = signal.iirnotch(f, self.q, self.sample_rate)
        self._f = SOSFilter(signal.tf2sos(b, a))

    def process(self, x):
        return self._f.process(x) if self.enabled else x


class ToneFilters:
    """Passa-altas (remove sub-tom CTCSS < 300 Hz) e passa-baixas de áudio."""

    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate
        self.highpass_enabled = False
        self.lowpass_hz = 0.0
        self._hp = SOSFilter(signal.butter(6, 300, "highpass", fs=sample_rate, output="sos"))
        self._lp = None

    def set_lowpass(self, hz: float):
        self.lowpass_hz = float(hz)
        if hz and hz < self.sample_rate / 2.1:
            self._lp = SOSFilter(signal.butter(6, hz, "lowpass", fs=self.sample_rate, output="sos"))
        else:
            self._lp = None

    def process(self, x):
        if self.highpass_enabled:
            x = self._hp.process(x)
        if self._lp is not None:
            x = self._lp.process(x)
        return x


class NoiseReduction:
    """Redução de ruído por subtração espectral (STFT com overlap-add).

    Estima o piso de ruído por bin com um mínimo seguido (minimum statistics
    simplificado) e aplica um ganho espectral suave. Latência = 1 quadro.
    """

    def __init__(self, sample_rate: float, frame: int = 512):
        self.sample_rate = sample_rate
        self.enabled = False
        self.strength = 1.5  # sobre-subtração
        self.frame = frame
        self.hop = frame // 2
        self.win = np.sqrt(signal.windows.hann(frame, sym=False)).astype(np.float32)
        self._in = np.zeros(0, np.float32)
        self._ola = np.zeros(frame, np.float32)
        self._noise = None
        self._gain_prev = None

    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled:
            self._in = np.zeros(0, np.float32)
            return x
        buf = np.concatenate((self._in, x.astype(np.float32)))
        out = []
        pos = 0
        while pos + self.frame <= len(buf):
            fr = buf[pos:pos + self.frame] * self.win
            spec = np.fft.rfft(fr)
            mag2 = np.abs(spec) ** 2
            if self._noise is None:
                self._noise = mag2.copy()
                self._gain_prev = np.ones_like(mag2)
            # acompanha o mínimo: desce rápido, sobe devagar
            self._noise = np.where(mag2 < self._noise,
                                   0.7 * self._noise + 0.3 * mag2,
                                   self._noise * 1.002 + 1e-12)
            g = 1.0 - self.strength * self._noise / (mag2 + 1e-12)
            g = np.clip(g, 0.08, 1.0)
            g = 0.6 * g + 0.4 * self._gain_prev  # suaviza no tempo (menos 'ruído musical')
            self._gain_prev = g
            y = np.fft.irfft(spec * g, self.frame).astype(np.float32) * self.win
            self._ola += y
            out.append(self._ola[:self.hop].copy())
            self._ola = np.concatenate((self._ola[self.hop:], np.zeros(self.hop, np.float32)))
            pos += self.hop
        self._in = buf[pos:]
        if not out:
            return np.zeros(0, np.float32)
        return np.concatenate(out)


def soft_limiter(x: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """Limitador suave (tanh) para evitar clipping na placa de som."""
    return (np.tanh(x / threshold) * threshold).astype(np.float32)
