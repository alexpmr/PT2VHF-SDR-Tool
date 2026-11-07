"""Modem AFSK 1200 baud (Bell 202) para APRS / packet radio."""
from __future__ import annotations

import numpy as np
from scipy import signal

from ..dsp.filters import Decimator, SOSFilter
from .ax25 import AX25Frame, HDLCDeframer, build_frame, hdlc_bits, nrzi_encode

MARK, SPACE, BAUD = 1200.0, 2200.0, 1200.0


def afsk_modulate(frame: AX25Frame, sample_rate: float = 48_000, amplitude: float = 0.5) -> np.ndarray:
    """Gera áudio AFSK de um quadro (usado no simulador e em testes)."""
    levels = np.array(nrzi_encode(hdlc_bits(build_frame(frame))))
    spb = sample_rate / BAUD
    n = int(len(levels) * spb)
    idx = np.minimum((np.arange(n) / spb).astype(int), len(levels) - 1)
    freq = np.where(levels[idx] == 1, MARK, SPACE)
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    return (amplitude * np.sin(phase)).astype(np.float32)


class AFSKDemodulator:
    """Demodulador AFSK1200 não-coerente com DPLL de relógio.

    Entrada: áudio FM demodulado a 48 kHz. Internamente opera a 9600 Hz (8 amostras/bit).
    Vários "fatiadores" com diferentes pesos mark/space compensam a ênfase do
    transmissor (técnica semelhante à usada pelo Dire Wolf).
    """

    RATE = 9600

    def __init__(self, on_frame, input_rate: int = 48_000):
        self.on_frame = on_frame
        self._dedup: dict[bytes, float] = {}
        self._t = 0.0
        self.dec = Decimator(input_rate // self.RATE, cutoff=0.9)
        self.bpf = SOSFilter(signal.butter(4, [900, 2500], "bandpass", fs=self.RATE, output="sos"))
        self.spb = self.RATE / BAUD  # 8
        n = int(round(self.spb))
        t = np.arange(n) / self.RATE
        self.k_mark = np.exp(-2j * np.pi * MARK * t)
        self.k_space = np.exp(-2j * np.pi * SPACE * t)
        self._hist = np.zeros(n - 1, np.float32)
        self.slicer_gains = [0.5, 0.7, 1.0, 1.4, 2.0]
        self._slicers = [_Slicer(self.spb, HDLCDeframer(self._got)) for _ in self.slicer_gains]

    def _got(self, frame: AX25Frame):
        key = frame.tnc2().encode("latin-1", "replace")
        last = self._dedup.get(key)
        if last is not None and self._t - last < 2.0:
            return
        self._dedup[key] = self._t
        if len(self._dedup) > 64:
            self._dedup = {k: v for k, v in self._dedup.items() if self._t - v < 5}
        self.on_frame(frame)

    def process(self, audio: np.ndarray):
        x = self.dec.process(audio)
        if len(x) == 0:
            return
        self._t += len(x) / self.RATE
        x = self.bpf.process(x)
        # normaliza amplitude (AGC simples)
        rms = np.sqrt(np.mean(x ** 2)) + 1e-9
        x = x / rms
        buf = np.concatenate((self._hist, x))
        self._hist = buf[-(len(self.k_mark) - 1):]
        m = np.abs(np.convolve(buf, self.k_mark[::-1], "valid"))
        s = np.abs(np.convolve(buf, self.k_space[::-1], "valid"))
        for g, sl in zip(self.slicer_gains, self._slicers):
            sl.process(m - g * s)


class _Slicer:
    """Recuperação de relógio (DPLL) + decodificação NRZI."""

    def __init__(self, spb: float, deframer: HDLCDeframer):
        self.spb = spb
        self.deframer = deframer
        self._phase = 0.0
        self._last_sym = 0
        self._last_bit_level = 0

    def process(self, d: np.ndarray):
        syms = (d > 0).astype(np.int8)
        step = 1.0 / self.spb
        phase = self._phase
        last = self._last_sym
        level_prev = self._last_bit_level
        push = self.deframer.push
        for s in syms.tolist():
            if s != last:
                # transição: puxa a fase para 0.5 (meio do bit fica na amostragem)
                phase += 0.3 * (0.5 - phase) if phase < 0.5 else -0.3 * (phase - 0.5)
                last = s
            phase += step
            if phase >= 1.0:
                phase -= 1.0
                push(1 if s == level_prev else 0)  # NRZI
                level_prev = s
        self._phase, self._last_sym, self._last_bit_level = phase, last, level_prev
