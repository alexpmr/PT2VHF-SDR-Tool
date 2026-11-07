"""Blocos DSP com estado (processamento contínuo bloco a bloco).

Todos os blocos aceitam arrays NumPy e mantêm o estado entre chamadas, de modo
que a saída é idêntica à de processar o sinal inteiro de uma só vez.
"""
from __future__ import annotations

import numpy as np
from scipy import signal


class NCO:
    """Oscilador numérico: desloca o sinal IQ em frequência (mixer)."""

    def __init__(self, sample_rate: float, freq: float = 0.0):
        self.sample_rate = float(sample_rate)
        self.freq = float(freq)
        self._phase = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        if self.freq == 0.0:
            return x
        w = -2.0 * np.pi * self.freq / self.sample_rate
        n = np.arange(len(x))
        ph = self._phase + w * n
        self._phase = float((self._phase + w * len(x)) % (2 * np.pi))
        return x * np.exp(1j * ph).astype(np.complex64)


class FIRFilter:
    """Filtro FIR com estado, usando convolução por FFT (overlap-save)."""

    def __init__(self, taps: np.ndarray):
        self.set_taps(taps)

    def set_taps(self, taps: np.ndarray):
        self.taps = np.asarray(taps)
        self._hist = None

    def process(self, x: np.ndarray) -> np.ndarray:
        if len(x) == 0:
            return x
        n_hist = len(self.taps) - 1
        if self._hist is None or self._hist.dtype != np.result_type(x, self.taps):
            self._hist = np.zeros(n_hist, dtype=np.result_type(x, self.taps))
        buf = np.concatenate((self._hist, x))
        self._hist = buf[len(buf) - n_hist:] if n_hist else buf[:0]
        if len(buf) < 4 * len(self.taps):
            y = np.convolve(buf, self.taps, mode="valid")
        else:
            y = signal.oaconvolve(buf, self.taps, mode="valid")
        return y.astype(np.result_type(x, np.float32), copy=False)


class Decimator:
    """Filtro passa-baixa + decimação inteira, com controle de fase entre blocos."""

    def __init__(self, factor: int, cutoff: float = 0.8, numtaps: int | None = None):
        self.factor = int(factor)
        if self.factor <= 1:
            self.filter = None
        else:
            if numtaps is None:
                numtaps = 8 * self.factor + 1
            taps = signal.firwin(numtaps, cutoff / self.factor)
            self.filter = FIRFilter(taps.astype(np.float32))
        self._phase = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        if self.filter is None:
            return x
        y = self.filter.process(x)
        out = y[self._phase::self.factor]
        self._phase = (self._phase - len(y)) % self.factor
        return out


class SOSFilter:
    """Filtro IIR (seções de segunda ordem) com estado."""

    def __init__(self, sos: np.ndarray):
        self.sos = np.asarray(sos, dtype=np.float64)
        self._zi = None

    def process(self, x: np.ndarray) -> np.ndarray:
        if len(x) == 0 or len(self.sos) == 0:
            return x
        if self._zi is None:
            self._zi = np.zeros((self.sos.shape[0], 2), dtype=np.result_type(x, np.float64))
        y, self._zi = signal.sosfilt(self.sos, x, zi=self._zi)
        return y.astype(x.dtype, copy=False)


class IIRFilter:
    """Filtro IIR b/a com estado."""

    def __init__(self, b, a):
        self.b = np.atleast_1d(np.asarray(b, dtype=np.float64))
        self.a = np.atleast_1d(np.asarray(a, dtype=np.float64))
        self._zi = None

    def process(self, x: np.ndarray) -> np.ndarray:
        if len(x) == 0:
            return x
        if self._zi is None:
            self._zi = np.zeros(max(len(self.a), len(self.b)) - 1,
                                dtype=np.result_type(x, np.float64))
        y, self._zi = signal.lfilter(self.b, self.a, x, zi=self._zi)
        return y.astype(x.dtype, copy=False)


def bandpass_complex_taps(sample_rate: float, low: float, high: float,
                          numtaps: int = 257) -> np.ndarray:
    """Taps FIR complexos que deixam passar apenas [low, high] Hz (pode ser assimétrico).

    Usado como filtro de canal: AM/FM (simétrico), USB (300..2800), LSB (-2800..-300).
    """
    if high <= low:
        high = low + 10.0
    center = 0.5 * (low + high)
    half = 0.5 * (high - low)
    nyq = sample_rate / 2.0
    cutoff = min(max(half / nyq, 1e-4), 0.999)
    lp = signal.firwin(numtaps, cutoff, window=("kaiser", 7.0))
    n = np.arange(numtaps) - (numtaps - 1) / 2.0
    return (lp * np.exp(2j * np.pi * center * n / sample_rate)).astype(np.complex64)


def deemphasis(sample_rate: float, tau: float) -> IIRFilter:
    """Filtro de de-ênfase de 1ª ordem (tau em segundos, ex.: 75e-6)."""
    # Transformação bilinear de H(s) = 1 / (1 + s*tau)
    wc = 1.0 / tau
    k = 2.0 * sample_rate
    wca = k * np.tan(wc / k)  # pré-distorção
    b0 = wca / (wca + k)
    a1 = (wca - k) / (wca + k)
    return IIRFilter([b0, b0], [1.0, a1])


class DCBlocker:
    """Remove nível DC (passa-altas de 1 polo)."""

    def __init__(self, r: float = 0.995):
        self.f = IIRFilter([1.0, -1.0], [1.0, -r])

    def process(self, x: np.ndarray) -> np.ndarray:
        return self.f.process(x)
