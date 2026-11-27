"""Zoom FFT do waterfall: DDC (mistura + filtro + decimação) da faixa visível.

Com zoom alto, a FFT da banda inteira tem poucos bins na tela (ex.: 2,4 MS/s
com FFT 32768 = 73 Hz/bin, só ~137 bins em 10 kHz) e o waterfall fica com
colunas largas e borradas. Aqui a faixa visível é trazida para banda base,
filtrada e decimada, e uma FFT própria dá ~2048 bins só na área visível.

Roda na thread de DSP apenas enquanto o zoom está ativo. O estado do NCO e do
filtro é contínuo entre blocos, então não há emendas no espectro.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import signal

from .receiver import _window

VIEW_BINS = 2048          # bins desejados na largura visível
MIN_NFFT, MAX_NFFT = 1024, 16384
COVER = 1.5               # a banda decimada cobre 1,5x a vista (pan sem refazer)


def native_bins_in_view(span_hz: float, fs: float, nfft: int) -> float:
    return span_hz * nfft / fs if fs > 0 else 0.0


def zoom_needed(view_center: float, span_hz: float, center: float, fs: float, nfft: int) -> bool:
    """Vale usar o zoom FFT? Só quando a FFT nativa tem poucos bins na vista."""
    if fs <= 0 or span_hz <= 0 or not math.isfinite(view_center):
        return False
    if native_bins_in_view(span_hz, fs, nfft) >= VIEW_BINS / 2:
        return False
    if span_hz * COVER * 2 > fs:
        return False
    return abs(view_center - center) + span_hz * COVER / 2 <= fs / 2 * 0.98


class ZoomSpectrum:
    """DDC contínuo de um trecho da banda + FFT de alta resolução."""

    def __init__(self, fs: float, center: float, zoom_center: float, span_hz: float):
        self.fs = float(fs)
        self.center = float(center)
        self.zoom_center = float(zoom_center)
        self.span = float(span_hz)
        total = max(2, int(self.fs // (self.span * COVER)))
        # Estágio 1: FIR polifásico barato (só calcula as saídas mantidas).
        # Estágio 2: Chebyshev II na taxa já reduzida.
        self.d1 = 8 if total >= 32 else 1
        self.d2 = max(2, total // self.d1)
        self.decim = self.d1 * self.d2
        self.fs_out = self.fs / self.decim
        want = VIEW_BINS * self.fs_out / self.span
        self.nfft = int(min(MAX_NFFT, max(MIN_NFFT, 2 ** math.ceil(math.log2(want)))))
        # Chebyshev II: passband plano; rejeição >= 80 dB a partir de 0,6*fs_out,
        # o que mantém as imagens dobradas fora da largura coberta.
        ws = min(0.95, 1.2 / self.d2)
        self._sos = signal.cheby2(10, 80, ws, btype="low", output="sos")
        self._zi = np.zeros((self._sos.shape[0], 2), dtype=np.complex128)
        if self.d1 > 1:
            self._h = signal.firwin(8 * self.d1, 1.0 / self.d1, window=("kaiser", 8.0)).astype(np.float32)
            self._hist = np.zeros(0, dtype=np.complex64)
            # Polifásico em float32: cada bloco de d1 taps vira uma matriz
            # (2*d1, 2) que leva pares (re, im) a (re, im) filtrados.
            hr = self._h[::-1]
            self._poly = []
            for k in range(len(hr) // self.d1):
                mat = np.zeros((2 * self.d1, 2), dtype=np.float32)
                mat[0::2, 0] = hr[k * self.d1:(k + 1) * self.d1]
                mat[1::2, 1] = hr[k * self.d1:(k + 1) * self.d1]
                self._poly.append(mat)
        self._lo_cache: tuple[int, np.ndarray] | None = None
        self._phase = 0.0
        self._skip = 0
        self._buf = np.zeros(self.nfft, dtype=np.complex64)
        self._filled = 0
        self._freq_off = self.zoom_center - self.center

    def covers(self, view_center: float, span_hz: float, center: float, fs: float) -> bool:
        """A vista atual ainda cabe neste DDC (pan pequeno, mesmo zoom)?"""
        if fs != self.fs or center != self.center:
            return False
        if not 0.8 <= span_hz / self.span <= 1.25:
            return False
        half = self.span * COVER / 2
        return abs(view_center - self.zoom_center) + span_hz / 2 <= half

    def feed(self, iq: np.ndarray):
        n = len(iq)
        if n == 0:
            return
        w = -2.0 * math.pi * self._freq_off / self.fs
        if self._lo_cache is None or self._lo_cache[0] != n:
            self._lo_cache = (n, np.exp(1j * w * np.arange(n)).astype(np.complex64))
        lo = self._lo_cache[1] * np.complex64(np.exp(1j * self._phase))
        self._phase = math.remainder(self._phase + w * n, 2 * math.pi)
        mixed = iq.astype(np.complex64, copy=False) * lo
        if self.d1 > 1:
            mixed = self._stage1(mixed)
            if not len(mixed):
                return
        m = len(mixed)
        y, self._zi = signal.sosfilt(self._sos, mixed, zi=self._zi)
        out = y[self._skip::self.d2].astype(np.complex64)
        self._skip = (self._skip - m) % self.d2
        k = len(out)
        if k >= self.nfft:
            self._buf[:] = out[-self.nfft:]
        elif k:
            self._buf[:-k] = self._buf[k:]
            self._buf[-k:] = out
        self._filled = min(self.nfft, self._filled + k)

    def _stage1(self, x: np.ndarray) -> np.ndarray:
        buf = np.concatenate((self._hist, x)) if len(self._hist) else x
        taps = len(self._h)
        if len(buf) < taps:
            self._hist = buf.copy()
            return buf[:0]
        nout = (len(buf) - taps) // self.d1 + 1
        d = self.d1
        ri = np.ascontiguousarray(buf, dtype=np.complex64).view(np.float32)
        acc = np.zeros((nout, 2), dtype=np.float32)
        for k, mat in enumerate(self._poly):
            seg = ri[2 * k * d:2 * (k * d + nout * d)].reshape(nout, 2 * d)
            acc += seg @ mat
        y = acc.view(np.complex64).ravel()
        self._hist = buf[nout * self.d1:].copy()
        return y.astype(np.complex64, copy=False)

    @property
    def ready(self) -> bool:
        return self._filled >= self.nfft

    def spectrum(self) -> np.ndarray | None:
        """Espectro em dBFS (fftshift), centrado em zoom_center, largura fs_out."""
        if not self.ready:
            return None
        win = _window("blackmanharris", self.nfft)
        p = np.abs(np.fft.fft(self._buf * win)) ** 2 / (np.sum(win) ** 2)
        return np.fft.fftshift(10 * np.log10(p + 1e-20)).astype(np.float32)
