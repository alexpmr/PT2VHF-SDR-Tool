"""Fontes sem hardware: simulador de banda (para demonstração/testes) e arquivo WAV IQ."""
from __future__ import annotations

import re
import time
import wave

import numpy as np

from ..decoders.afsk import afsk_modulate
from ..decoders.ax25 import AX25Frame
from .base import IQSource, SourceError

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.",
    "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.",
    "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-",
    "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..", "0": "-----",
    "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
    "7": "--...", "8": "---..", "9": "----.", "/": "-..-.",
}


def morse_keying(text: str, wpm: float = 18) -> np.ndarray:
    """Sequência on/off com uma unidade (dit) por elemento."""
    units: list[int] = []
    for word in text.upper().split():
        for ch in word:
            for sym in MORSE.get(ch, ""):
                units += [1] * (1 if sym == "." else 3) + [0]
            units += [0, 0]
        units += [0] * 4
    return np.array(units + [0] * 20, np.float32)


class SimulatorSource(IQSource):
    """Gera uma banda sintética com sinais realistas (frequências absolutas).

    - 145.570 MHz NFM: pacotes APRS (AFSK1200) a cada 6 s
    - 145.430 MHz NFM: tons de voz com CTCSS 88.5 Hz e sequência DTMF
    - 145.800 MHz CW: baliza "CQ DE PT2VHF"
    - 145.650 MHz AM: tom de 1 kHz
    - 145.250 MHz USB: dois tons (700 + 1900 Hz)
    - 98.100 MHz WFM: emissora com acordes musicais
    """

    name = "Simulador"
    supports_gain = True
    gains_db = [0.0, 10.0, 20.0, 30.0, 40.0]

    def __init__(self, sample_rate: int = 1_200_000, center_freq: float = 145.5e6,
                 realtime: bool = True, noise_db: float = -60.0):
        super().__init__(sample_rate, center_freq)
        self.realtime = realtime
        self.noise_db = noise_db
        self._n = 0  # índice absoluto de amostras
        self._phases: dict[str, float] = {}
        self._rng = np.random.default_rng(1234)
        self.gain_db = 30.0
        self._aprs_frames = [
            AX25Frame("PY2SIM-9", "APRS", ["WIDE1-1", "WIDE2-1"],
                      b"!2332.55S/04638.07W>090/036/A=002500 PT2VHF SDR Tool - teste"),
            AX25Frame("PY2SIM-7", "RSS25U", ["WIDE1-1"], b"`JB#oXv>/Mic-E simulado"),
            AX25Frame("PY2WX", "APRS", ["WIDE2-1"],
                      b"!2330.00S/04640.00W_220/004g010t077r000p000h65b10150Estacao WX"),
            AX25Frame("PY2TLM", "APRS", [], b"T#123,199,000,255,073,123,01101001Telemetria"),
            AX25Frame("PY2ABC", "APRS", ["WIDE2-2"], b":PY2XYZ   :Ola, QSL? 73{01"),
        ]
        self._aprs_audio = [afsk_modulate(f, 48_000, 0.8) for f in self._aprs_frames]
        self._cw = morse_keying("CQ CQ DE PT2VHF PT2VHF K")
        dtmf = "1479#"
        self._dtmf_seq = dtmf

    def set_gain(self, db):
        self.gain_db = 30.0 if db is None else float(db)

    # ------------------------------------------------------------- geração
    def _fm(self, key, t, off, mod_hz_dev):
        """Sinal FM: mod_hz_dev é o desvio instantâneo em Hz (array)."""
        fs = self.sample_rate
        inc = 2 * np.pi * (off + mod_hz_dev) / fs
        ph = self._phases.get(key, 0.0) + np.cumsum(inc)
        self._phases[key] = float(ph[-1] % (2 * np.pi))
        return np.exp(1j * ph)

    def _carrier(self, key, off, n):
        fs = self.sample_rate
        w = 2 * np.pi * off / fs
        p0 = self._phases.get(key, 0.0)
        ph = p0 + w * np.arange(n)
        self._phases[key] = float((p0 + w * n) % (2 * np.pi))
        return np.exp(1j * ph)

    def generate(self, n: int) -> np.ndarray:
        fs = self.sample_rate
        t = (self._n + np.arange(n)) / fs
        self._n += n
        g = 10 ** ((self.gain_db - 30) / 20)
        nl = 10 ** (self.noise_db / 20) / np.sqrt(2)
        x = (self._rng.normal(0, nl, n) + 1j * self._rng.normal(0, nl, n)).astype(np.complex64)
        half = fs / 2 * 0.98

        def inside(f):
            return abs(f - self.center_freq) < half

        def off(f):
            return f - self.center_freq

        # APRS 145.570: um pacote a cada 6 s, alternando tipos
        f = 145.570e6
        if inside(f):
            period = 6.0
            slot = (t // period).astype(int)
            tin = t - slot * period
            k = int(slot[0]) % len(self._aprs_audio)
            aud = self._aprs_audio[k]
            idx = (tin * 48_000).astype(int)
            active = idx < len(aud)
            m = np.where(active, aud[np.minimum(idx, len(aud) - 1)], 0.0)
            sig = self._fm("aprs", t, off(f), 3000 * m)
            x += (0.05 * g * sig * active).astype(np.complex64)

        # Voz simulada 145.430 + CTCSS 88.5 + DTMF
        f = 145.430e6
        if inside(f):
            period = 10.0
            tin = t % period
            on = tin < 7.0
            melody = np.array([440, 523.25, 659.25, 587.33, 493.88, 392.0])
            fr = melody[(tin * 2).astype(int) % len(melody)]
            voice = 0.6 * np.sin(2 * np.pi * fr * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
            # DTMF entre 4 e 6.5 s
            lows = {"1": 697, "4": 770, "7": 852, "9": 852, "#": 941}
            highs = {"1": 1209, "4": 1209, "7": 1209, "9": 1477, "#": 1477}
            dt_idx = ((tin - 4.0) / 0.5).astype(int)
            dt_on = (tin >= 4.0) & (tin < 6.5) & (((tin - 4.0) % 0.5) < 0.3)
            fl = np.array([lows[c] for c in self._dtmf_seq])[np.clip(dt_idx, 0, 4)]
            fh = np.array([highs[c] for c in self._dtmf_seq])[np.clip(dt_idx, 0, 4)]
            dtmf = 0.4 * (np.sin(2 * np.pi * fl * t) + np.sin(2 * np.pi * fh * t))
            audio = np.where(dt_on, dtmf, np.where((tin >= 4.0) & (tin < 6.5), 0, voice))
            ctcss = 0.15 * np.sin(2 * np.pi * 88.5 * t)
            sig = self._fm("voice", t, off(f), 3000 * audio + 5000 * ctcss)
            x += (0.08 * g * sig * on).astype(np.complex64)

        # CW 145.800
        f = 145.800e6
        if inside(f):
            unit = 1.2 / 18
            idx = (t / unit).astype(int) % len(self._cw)
            key = self._cw[idx]
            x += (0.03 * g * key * self._carrier("cw", off(f), n)).astype(np.complex64)

        # AM 145.650
        f = 145.650e6
        if inside(f):
            env = 1 + 0.7 * np.sin(2 * np.pi * 1000 * t)
            x += (0.03 * g * env * self._carrier("am", off(f), n)).astype(np.complex64)

        # USB 145.250: dois tons
        f = 145.250e6
        if inside(f):
            a = self._carrier("usb1", off(f) + 700, n) + self._carrier("usb2", off(f) + 1900, n)
            x += (0.02 * g * a).astype(np.complex64)

        # WFM 98.1 MHz
        f = 98.1e6
        if inside(f):
            chord = sum(np.sin(2 * np.pi * h * t) for h in (261.6, 329.6, 392.0))
            mus = 0.3 * chord * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
            sig = self._fm("wfm", t, off(f), 50_000 * mus)
            x += (0.2 * g * sig).astype(np.complex64)
        return x

    def _run(self):
        t0 = time.monotonic()
        produced = 0
        while self._running:
            blk = self.generate(self.block_size)
            produced += len(blk)
            self._push(blk)
            if self.realtime:
                ahead = produced / self.sample_rate - (time.monotonic() - t0)
                if ahead > 0:
                    time.sleep(ahead)


class WavIQSource(IQSource):
    """Reproduz gravações IQ em WAV estéreo (I=esquerdo, Q=direito), ex.: SDR#, SDR++."""

    name = "Arquivo IQ"
    tunable = False

    def __init__(self, path: str, center_freq: float | None = None, loop: bool = True):
        try:
            self.wav = wave.open(path, "rb")
        except (wave.Error, OSError) as e:
            raise SourceError(f"Arquivo inválido: {e}") from e
        if self.wav.getnchannels() != 2:
            raise SourceError("O WAV IQ precisa ter 2 canais (I/Q)")
        fs = self.wav.getframerate()
        if center_freq is None:
            m = re.search(r"(\d{6,11})\s*Hz", path, re.IGNORECASE)
            center_freq = float(m.group(1)) if m else 100e6
        super().__init__(fs, center_freq)
        self.width = self.wav.getsampwidth()
        self.loop = loop
        self.path = path

    def check_freq(self, hz):
        half = self.sample_rate / 2
        if self.center_freq - half <= hz <= self.center_freq + half:
            return ""
        return "Arquivo IQ: frequência fora da largura gravada; fonte não sintonizável."

    def _read_block(self):
        frames = self.wav.readframes(self.block_size)
        if len(frames) == 0:
            if not self.loop:
                return None
            self.wav.rewind()
            frames = self.wav.readframes(self.block_size)
        if self.width == 1:
            a = (np.frombuffer(frames, np.uint8).astype(np.float32) - 127.5) / 128
        elif self.width == 2:
            a = np.frombuffer(frames, "<i2").astype(np.float32) / 32768
        elif self.width == 4:
            a = np.frombuffer(frames, "<i4").astype(np.float32) / 2 ** 31
        else:
            raise SourceError("Formato WAV não suportado")
        return (a[0::2] + 1j * a[1::2]).astype(np.complex64)

    def _run(self):
        t0 = time.monotonic()
        produced = 0
        while self._running:
            blk = self._read_block()
            if blk is None:
                break
            produced += len(blk)
            self._push(blk)
            ahead = produced / self.sample_rate - (time.monotonic() - t0)
            if ahead > 0:
                time.sleep(ahead)
        self._running = False

    def close(self):
        super().close()
        self.wav.close()
