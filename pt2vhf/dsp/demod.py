"""Demoduladores, AGC, noise blanker e squelch."""
from __future__ import annotations

import numpy as np

from .filters import DCBlocker


class FMDemod:
    """Discriminador de quadratura (FM). Saída normalizada pelo desvio."""

    def __init__(self, sample_rate: float, deviation: float):
        self.sample_rate = sample_rate
        self.deviation = deviation
        self._last = np.complex64(1.0)

    def process(self, x: np.ndarray) -> np.ndarray:
        if len(x) == 0:
            return np.zeros(0, np.float32)
        prev = np.concatenate(([self._last], x[:-1]))
        self._last = x[-1]
        d = np.angle(x * np.conj(prev))
        gain = self.sample_rate / (2 * np.pi * self.deviation)
        return (d * gain).astype(np.float32)


class AMDemod:
    """Detector de envoltória com remoção de DC."""

    def __init__(self):
        self.dc = DCBlocker(0.999)

    def process(self, x: np.ndarray) -> np.ndarray:
        return self.dc.process(np.abs(x).astype(np.float32))


class SSBDemod:
    """SSB/CW: o filtro de canal já seleciona a banda lateral; aqui somamos o BFO
    (deslocamento de tom, usado em CW) e tomamos a parte real."""

    def __init__(self, sample_rate: float, bfo: float = 0.0):
        self.sample_rate = sample_rate
        self.bfo = bfo
        self._phase = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        if self.bfo:
            w = 2 * np.pi * self.bfo / self.sample_rate
            ph = self._phase + w * np.arange(len(x))
            self._phase = float((self._phase + w * len(x)) % (2 * np.pi))
            x = x * np.exp(1j * ph)
        return np.real(x).astype(np.float32)


class AGC:
    """AGC com ataque rápido, tempo de 'hang' e decaimento configurável.

    Trabalha em sub-blocos de ~5 ms (vetorizado) e interpola o ganho.
    """

    PRESETS = {  # decay (s), hang (s)
        "Rápido": (0.05, 0.05),
        "Médio": (0.3, 0.2),
        "Lento": (1.0, 0.5),
    }

    def __init__(self, sample_rate: float, target: float = 0.3, max_gain_db: float = 80.0):
        self.sample_rate = sample_rate
        self.target = target
        self.max_gain = 10 ** (max_gain_db / 20)
        self.enabled = True
        self.set_speed("Médio")
        self._peak = 1e-6
        self._hang_left = 0.0
        self._last_gain = 1.0
        self.manual_gain_db = 0.0

    def set_speed(self, name: str):
        self.decay, self.hang = self.PRESETS.get(name, self.PRESETS["Médio"])

    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return x * np.float32(10 ** (self.manual_gain_db / 20))
        n = len(x)
        if n == 0:
            return x
        sub = max(1, int(self.sample_rate * 0.005))
        nblk = int(np.ceil(n / sub))
        pad = np.zeros(nblk * sub, np.float32)
        pad[:n] = np.abs(x)
        peaks = pad.reshape(nblk, sub).max(axis=1)
        dt = sub / self.sample_rate
        decay_k = np.exp(-dt / max(self.decay, 1e-3))
        gains = np.empty(nblk, np.float32)
        p = self._peak
        hang = self._hang_left
        for i, v in enumerate(peaks):
            if v > p:
                p = v  # ataque instantâneo
                hang = self.hang
            elif hang > 0:
                hang -= dt
            else:
                p = max(p * decay_k, v, 1e-7)
            gains[i] = min(self.target / p, self.max_gain)
        self._peak, self._hang_left = p, hang
        # interpola ganho por amostra (suave entre sub-blocos)
        pts = np.concatenate(([self._last_gain], gains))
        xs = np.arange(nblk + 1) * sub
        g = np.interp(np.arange(n) + sub, xs, pts).astype(np.float32)
        self._last_gain = float(gains[-1])
        return x * g


class NoiseBlanker:
    """Noise blanker no IQ: zera impulsos acima de N vezes a média da magnitude."""

    def __init__(self, threshold: float = 6.0):
        self.enabled = False
        self.threshold = threshold
        self._avg = None

    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled or len(x) == 0:
            return x
        mag = np.abs(x)
        avg = float(np.median(mag)) + 1e-12
        if self._avg is None:
            self._avg = avg
        self._avg = 0.8 * self._avg + 0.2 * avg
        mask = mag > self.threshold * self._avg
        if np.any(mask):
            # alarga a máscara ±2 amostras para pegar as bordas do impulso
            idx = np.flatnonzero(mask)
            for d in (-2, -1, 1, 2):
                j = np.clip(idx + d, 0, len(x) - 1)
                mask[j] = True
            x = x.copy()
            x[mask] = 0
        return x


class Squelch:
    """Squelch por nível (dBFS) com histerese e retardo de fechamento."""

    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate
        self.threshold_db = -150.0  # aberto
        self.hysteresis_db = 3.0
        self.tail = 0.25  # segundos
        self.is_open = True
        self._tail_left = 0.0

    def update(self, level_db: float, nsamples: int) -> bool:
        if self.threshold_db <= -149.0:
            self.is_open = True
            return True
        dt = nsamples / self.sample_rate
        if level_db >= self.threshold_db:
            self.is_open = True
            self._tail_left = self.tail
        elif level_db < self.threshold_db - self.hysteresis_db:
            if self._tail_left > 0:
                self._tail_left -= dt
            else:
                self.is_open = False
        return self.is_open


def power_db(x: np.ndarray) -> float:
    if len(x) == 0:
        return -150.0
    p = float(np.mean(np.real(x) ** 2 + np.imag(x) ** 2))
    return 10 * np.log10(p + 1e-20)


def dbfs_to_s_units(dbfs: float, calibration_db: float = 0.0) -> tuple[float, str]:
    """Converte dBFS em dBm aproximado (com calibração) e texto S-meter.

    Convenção IARU VHF/UHF: S9 = -93 dBm, 6 dB por unidade S.
    """
    dbm = dbfs - 45.0 + calibration_db  # offset nominal (RTL-SDR, ganho médio; ajuste em s_meter_cal)
    s9 = -93.0
    if dbm <= s9:
        s = max(0.0, 9 + (dbm - s9) / 6.0)
        return dbm, f"S{int(s)}"
    over = dbm - s9
    return dbm, f"S9+{int(over)}"
