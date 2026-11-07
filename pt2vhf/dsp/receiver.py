"""Cadeia completa de recepção: IQ bruto -> canal -> demodulação -> áudio 48 kHz."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

from .audiofx import Equalizer, NoiseReduction, Notch, ToneFilters, soft_limiter
from .demod import AGC, AMDemod, FMDemod, NoiseBlanker, SSBDemod, Squelch, power_db
from .filters import Decimator, FIRFilter, NCO, SOSFilter, bandpass_complex_taps, deemphasis

IF_RATE = 240_000
AUDIO_RATE = 48_000

# Taxas de amostragem suportadas: múltiplos inteiros de 240 kHz (decimação exata).
SAMPLE_RATES = [240_000, 960_000, 1_200_000, 1_440_000, 1_920_000, 2_400_000, 2_880_000]


@dataclass
class ModeInfo:
    name: str
    low: float      # borda inferior padrão do filtro (Hz, relativa à portadora)
    high: float     # borda superior padrão
    step: int       # passo de sintonia padrão (Hz)
    bw_presets: tuple


MODES = {
    "NFM": ModeInfo("NFM", -6000, 6000, 12500, (6000, 8000, 11000, 12500, 16000)),
    "WFM": ModeInfo("WFM", -90000, 90000, 100000, (120000, 150000, 180000)),
    "AM": ModeInfo("AM", -4500, 4500, 5000, (3000, 6000, 9000, 12000)),
    "USB": ModeInfo("USB", 300, 2800, 100, (1800, 2400, 2700, 3000)),
    "LSB": ModeInfo("LSB", -2800, -300, 100, (1800, 2400, 2700, 3000)),
    "CW": ModeInfo("CW", -250, 250, 10, (100, 250, 500, 1000)),
    "DSB": ModeInfo("DSB", -3000, 3000, 100, (4000, 6000)),
    "RAW": ModeInfo("RAW", -12000, 12000, 1000, (24000,)),
}


def passband_for(mode: str, width: float) -> tuple[float, float]:
    """Calcula (low, high) para uma largura total em Hz no modo indicado."""
    if mode == "USB":
        return 300.0, 300.0 + width
    if mode == "LSB":
        return -300.0 - width, -300.0
    return -width / 2.0, width / 2.0


class Receiver:
    """Recebe blocos IQ na taxa da fonte e produz áudio a 48 kHz."""

    def __init__(self, input_rate: int):
        self.input_rate = int(input_rate)
        if self.input_rate % IF_RATE:
            raise ValueError(f"Taxa {input_rate} não é múltiplo de {IF_RATE}")
        self.offset_hz = 0.0  # frequência VFO - frequência central
        self.mode = "NFM"
        self.low, self.high = MODES["NFM"].low, MODES["NFM"].high
        self.cw_pitch = 700.0
        self.wfm_deemph_tau = 75e-6  # Américas (Brasil): 75 µs
        self.nfm_deemph = False
        self.volume = 0.5
        self.muted = False
        self.signal_db = -150.0
        self.rec_audio = np.zeros(0, np.float32)
        self.keep_if = False
        self.last_if = np.zeros(0, np.complex64)
        self.nco = NCO(self.input_rate)
        self.stage1 = Decimator(self.input_rate // IF_RATE, cutoff=0.85,
                                numtaps=12 * (self.input_rate // IF_RATE) + 1)
        self.nb = NoiseBlanker()
        self.agc = AGC(AUDIO_RATE)
        self.squelch = Squelch(AUDIO_RATE)
        self.eq = Equalizer(AUDIO_RATE)
        self.nr = NoiseReduction(AUDIO_RATE)
        self.notch = Notch(AUDIO_RATE)
        self.tones = ToneFilters(AUDIO_RATE)
        self._build_mode()

    # ------------------------------------------------------------------ config
    def set_offset(self, hz: float):
        self.offset_hz = float(hz)
        self.nco.freq = self.offset_hz

    def set_mode(self, mode: str, width: float | None = None):
        if mode not in MODES:
            raise ValueError(mode)
        self.mode = mode
        if width is None:
            self.low, self.high = MODES[mode].low, MODES[mode].high
        else:
            self.low, self.high = passband_for(mode, width)
        self._build_mode()

    def set_passband(self, low: float, high: float):
        self.low, self.high = float(low), float(high)
        self._build_channel_filter()

    @property
    def bandwidth(self) -> float:
        return self.high - self.low

    def _build_mode(self):
        m = self.mode
        if m == "WFM":
            self.ch_rate = IF_RATE
            self.dec_if = None
            self.demod = FMDemod(IF_RATE, 75_000)
            self.deemph = deemphasis(IF_RATE, self.wfm_deemph_tau)
            self.wfm_lp = SOSFilter(signal.butter(8, 15_000, fs=IF_RATE, output="sos"))
            self.wfm_dec = Decimator(IF_RATE // AUDIO_RATE, cutoff=0.9)
        else:
            self.ch_rate = AUDIO_RATE
            self.dec_if = Decimator(IF_RATE // AUDIO_RATE, cutoff=0.9, numtaps=61)
            if m == "NFM":
                self.demod = FMDemod(AUDIO_RATE, 5_000 if self.bandwidth > 9000 else 2_500)
            elif m in ("AM",):
                self.demod = AMDemod()
            elif m == "CW":
                self.demod = SSBDemod(AUDIO_RATE, bfo=self.cw_pitch)
            elif m == "RAW":
                self.demod = SSBDemod(AUDIO_RATE)
            else:  # USB, LSB, DSB
                self.demod = SSBDemod(AUDIO_RATE)
            self.deemph = deemphasis(AUDIO_RATE, 750e-6)
        self.agc.enabled_for_mode = m in ("AM", "USB", "LSB", "CW", "DSB", "RAW")
        self._build_channel_filter()

    def _build_channel_filter(self):
        low, high = self.low, self.high
        nyq = self.ch_rate / 2 * 0.95
        low, high = max(low, -nyq), min(high, nyq)
        ntaps = 129 if self.mode == "WFM" else 257
        self.chan = FIRFilter(bandpass_complex_taps(self.ch_rate, low, high, ntaps))
        if self.mode == "NFM" and isinstance(self.demod, FMDemod):
            self.demod.deviation = 5_000 if (high - low) > 9000 else 2_500

    # --------------------------------------------------------------- processo
    def process(self, iq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Processa um bloco IQ. Retorna (áudio_saída, áudio_para_decodificadores)."""
        x = self.nco.process(iq)
        x = self.stage1.process(x)
        if self.keep_if:  # IQ a 240 kHz centrado no VFO (assistente de sintonia)
            self.last_if = x
        x = self.nb.process(x)
        if self.mode == "WFM":
            x = self.chan.process(x)
            self.signal_db = power_db(x)
            a = self.demod.process(x)
            a = self.deemph.process(a)
            a = self.wfm_lp.process(a)
            a = self.wfm_dec.process(a)
            raw = a
        else:
            x = self.dec_if.process(x)
            x = self.chan.process(x)
            self.signal_db = power_db(x)
            a = self.demod.process(x)
            raw = a
            if self.mode == "NFM" and self.nfm_deemph:
                a = self.deemph.process(a)
            if self.agc.enabled_for_mode:
                a = self.agc.process(a)
            else:
                a = a * np.float32(0.5)
        open_ = self.squelch.update(self.signal_db, len(a))
        a = self.tones.process(a)
        a = self.notch.process(a)
        a = self.nr.process(a)
        a = self.eq.process(a)
        # áudio para gravação: independe do volume e do mudo
        self.rec_audio = soft_limiter(a) if open_ else np.zeros_like(a)
        if not open_ or self.muted:
            a = np.zeros_like(a)
        else:
            a = soft_limiter(a * np.float32(self.volume * 2.0))
        return a.astype(np.float32), raw.astype(np.float32)


def compute_spectrum(iq: np.ndarray, nfft: int, max_frames: int = 8,
                     window: str = "blackmanharris") -> np.ndarray | None:
    """Espectro médio em dBFS (bins com fftshift: -fs/2 .. +fs/2)."""
    nfr = min(len(iq) // nfft, max_frames)
    if nfr < 1:
        return None
    w = _window(window, nfft)
    step = len(iq) // nfr
    frames = np.stack([iq[i * step:i * step + nfft] for i in range(nfr)])
    spec = np.fft.fft(frames * w, axis=1)
    p = np.mean(np.abs(spec) ** 2, axis=0) / (np.sum(w) ** 2)
    return np.fft.fftshift(10 * np.log10(p + 1e-20)).astype(np.float32)


_WIN_CACHE: dict = {}


def _window(name: str, n: int) -> np.ndarray:
    key = (name, n)
    if key not in _WIN_CACHE:
        _WIN_CACHE[key] = signal.get_window(name, n).astype(np.float32)
    return _WIN_CACHE[key]
