"""ACARS (VHF AM, MSK 2400 bit/s) decodificado nativamente do IQ do SDR.

Implementação própria: canal AM de cada frequência (131,550 / 131,725 /
131,825 MHz cabem juntas em 2,4 MS/s), discriminador de tom 1200/2400 Hz por
bit, codificação diferencial do MSK (tom 2400 Hz = bit igual ao anterior),
sincronismo ``+*`` SYN SYN SOH, paridade ímpar e BCS CRC-16 (Kermit). Só
entrega blocos com CRC válido. Um modo por vez: o SDR é sintonizado na faixa
ACARS; as três frequências são decodificadas em paralelo nessa faixa.
"""
from __future__ import annotations

import math
import queue
import threading
import time

import numpy as np

ACARS_FREQS_HZ = (131_550_000, 131_725_000, 131_825_000)
AUDIO_RATE = 48_000
BAUD = 2400
_SYNC = bytes((0xAB, 0x2A, 0x16, 0x16, 0x01))   # '+'|paridade, '*', SYN, SYN, SOH
_ETX, _ETB, _STX = 0x83, 0x97, 0x02


def odd_parity(c: int) -> int:
    c &= 0x7F
    return c | (0x80 if bin(c).count("1") % 2 == 0 else 0)


def crc_kermit(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc


def build_block(mode: str = "2", address: str = ".PP-XYZ", ack: str = "\x15",
                label: str = "H1", block_id: str = "1", text: str = "") -> bytes:
    """Bloco ACARS completo (pré-chave, sincronismo, BCS, DEL) para testes."""
    head = mode + address[:7].rjust(7, ".") + ack + label[:2] + block_id
    body = bytes(odd_parity(ord(c)) for c in head)
    if text:
        body += bytes((odd_parity(_STX),)) + bytes(odd_parity(ord(c)) for c in text)
    body += bytes((_ETX,))
    crc = crc_kermit(body)
    return bytes([0xFF] * 16) + _SYNC + body + bytes((crc & 0xFF, crc >> 8, 0x7F))


def block_tones(block: bytes) -> list[int]:
    """Bits LSB primeiro -> tons (1 = 2400 Hz quando o bit repete o anterior)."""
    tones, prev = [], 1
    for byte in block:
        for k in range(8):
            bit = (byte >> k) & 1
            tones.append(1 ^ bit ^ prev)
            prev = bit
    return tones


def synth_acars_audio(blocks, rate: int = AUDIO_RATE, gap_s: float = 0.3) -> np.ndarray:
    parts = [np.zeros(int(gap_s * rate))]
    sps = rate / BAUD
    for block in blocks:
        tones = np.array(block_tones(block))
        n = int(len(tones) * sps)
        idx = np.minimum((np.arange(n) / sps).astype(np.int64), len(tones) - 1)
        freq = np.where(tones[idx] == 1, 2400.0, 1200.0)
        parts.append(np.sin(2 * math.pi * np.cumsum(freq) / rate))
        parts.append(np.zeros(int(gap_s * rate)))
    return np.concatenate(parts)


def synth_acars_iq(blocks, sample_rate: int = 2_400_000, center_hz: float = 131_700_000,
                   station_hz: float = ACARS_FREQS_HZ[0], depth: float = 0.6,
                   snr_db: float = 25.0, seed: int = 0) -> np.ndarray:
    """IQ AM (portadora + MSK de áudio) de blocos ACARS, para testes/autoteste."""
    audio = synth_acars_audio(blocks, AUDIO_RATE)
    up = int(round(sample_rate / AUDIO_RATE))
    env = 1.0 + depth * np.repeat(audio, up)
    rng = np.random.default_rng(seed)
    t = np.arange(env.size) / sample_rate
    sig = 0.25 * env * np.exp(1j * (2 * math.pi * (station_hz - center_hz) * t + 0.3))
    noise = 0.25 * 10 ** (-snr_db / 20) / math.sqrt(2)
    sig = sig + noise * (rng.standard_normal(env.size) + 1j * rng.standard_normal(env.size))
    return sig.astype(np.complex64)


def parse_block(body: bytes, crc_bytes: bytes) -> dict | None:
    """Campos do bloco (sem paridade) se paridade e BCS forem válidos."""
    if crc_kermit(body + crc_bytes) != 0:
        return None
    if any(bin(b).count("1") % 2 == 0 for b in body):
        return None
    chars = bytes(b & 0x7F for b in body[:-1]).decode("ascii", errors="replace")
    if len(chars) < 12:
        return None
    msg = {"mode": chars[0], "reg": chars[1:8].lstrip("."), "ack": chars[8],
           "label": chars[9:11].replace("\x7f", "d"), "block_id": chars[11], "text": "",
           "end": "ETB" if body[-1] == _ETB else "ETX"}
    rest = chars[12:]
    if rest.startswith("\x02"):
        text = rest[1:]
        if msg["block_id"].isdigit() and len(text) >= 10:   # enlace descendente
            msg["msg_no"], msg["flight"] = text[:4], text[4:10].strip()
            text = text[10:]
        msg["text"] = text
    msg["ack"] = "NAK" if msg["ack"] == "\x15" else msg["ack"]
    return msg


def _fix_one_char(body: bytes, crc_bytes: bytes) -> dict | None:
    """Corrige 1 bit num único caractere com erro de paridade (validado pelo CRC)."""
    bad = [i for i, b in enumerate(body) if bin(b).count("1") % 2 == 0]
    if len(bad) != 1:
        return None
    i = bad[0]
    for k in range(8):
        fixed = bytearray(body)
        fixed[i] ^= 1 << k
        msg = parse_block(bytes(fixed), crc_bytes)
        if msg:
            msg["corrected"] = True
            return msg
    return None


class AcarsDemodulator:
    """Áudio AM (48 kHz) -> blocos ACARS com CRC válido."""

    WINDOW_S = 2.0
    STEP_S = 1.0

    def __init__(self, rate: int = AUDIO_RATE):
        self.rate = int(rate)
        self.sps = self.rate / BAUD
        self._buf = np.empty(0, dtype=np.float32)
        self._recent: dict[tuple, float] = {}
        self._clock = 0.0
        self.blocks = 0

    def process(self, audio) -> list[dict]:
        self._buf = np.concatenate((self._buf, np.asarray(audio, dtype=np.float32)))
        window, step = int(self.WINDOW_S * self.rate), int(self.STEP_S * self.rate)
        out = []
        while self._buf.size >= window:
            out += self._decode_window(self._buf[:window])
            self._buf = self._buf[step:]
            self._clock += self.STEP_S
        return out

    def flush(self) -> list[dict]:
        out = self._decode_window(self._buf) if self._buf.size > self.rate // 4 else []
        self._buf = np.empty(0, dtype=np.float32)
        return out

    def _decode_window(self, audio) -> list[dict]:
        x = np.asarray(audio, dtype=np.float64) - np.mean(audio)
        if not np.any(x):
            return []
        # Sinal analítico limitado a 600-3000 Hz (FFT): elimina CC, voz grave e ruído alto.
        n = x.size
        spec = np.fft.fft(x)
        freqs = np.fft.fftfreq(n, 1 / self.rate)
        spec[(freqs < 600) | (freqs > 3000)] = 0
        analytic = np.fft.ifft(spec)
        # Discriminador por produto conjugado: média complexa por bit (robusta a cliques).
        prod = analytic[1:] * np.conj(analytic[:-1])
        csum = np.concatenate(([0.0], np.cumsum(prod)))
        nbits = int((prod.size - self.sps) // self.sps)
        if nbits < 200:
            return []
        grid = np.arange(csum.size)
        center = np.exp(-2j * math.pi * 1800 / self.rate)
        best, best_score = None, -1.0
        for phase in np.arange(0, self.sps, self.sps / 16):
            edges = phase + np.arange(nbits + 1) * self.sps
            acc = np.diff(np.interp(edges, grid, csum.real) + 1j * np.interp(edges, grid, csum.imag))
            vals = np.angle(acc * center)           # >0: acima de 1800 Hz (tom 2400)
            score = float(np.mean(np.abs(vals)))
            if score > best_score:
                best, best_score = vals, score
        tones = (best > 0).astype(np.uint8)
        # b_k = b_{k-1} XOR (1 - t_k): MSK diferencial; tenta as duas polaridades.
        bits = np.bitwise_xor.accumulate(1 - tones) ^ 1
        found = []
        for stream in (bits, bits ^ 1):
            found += self._frames(stream)
        result = []
        now = self._clock
        for key in [k for k, t in self._recent.items() if now - t > 5]:
            del self._recent[key]
        for msg in found:
            key = (msg["reg"], msg["label"], msg["block_id"], msg["text"])
            if key in self._recent:
                continue
            self._recent[key] = now
            self.blocks += 1
            result.append(msg)
        return result

    @staticmethod
    def _frames(bits: np.ndarray) -> list[dict]:
        out = []
        sync_bits = np.unpackbits(np.frombuffer(_SYNC, dtype=np.uint8), bitorder="little")
        if bits.size < sync_bits.size + 120:
            return out
        windows = np.lib.stride_tricks.sliding_window_view(bits, sync_bits.size)
        for start in np.flatnonzero(np.all(windows == sync_bits, axis=1)):
            pos = int(start) + sync_bits.size
            nbytes = (bits.size - pos) // 8
            data = np.packbits(bits[pos:pos + nbytes * 8], bitorder="little").tobytes()
            for end, byte in enumerate(data[:240]):
                if byte in (_ETX, _ETB) and end >= 12:
                    if end + 3 <= len(data):
                        msg = parse_block(data[:end + 1], data[end + 1:end + 3])
                        if msg is None:
                            msg = _fix_one_char(data[:end + 1], data[end + 1:end + 3])
                        if msg:
                            out.append(msg)
                    break
        return out


class AcarsReceiver:
    """Recebe as três frequências ACARS do IQ atual numa thread própria."""

    def __init__(self, sample_rate: int, on_message, on_status=None, freqs=ACARS_FREQS_HZ):
        from ..sonde_rx import ChannelIQ
        self.channels = [(f, ChannelIQ(sample_rate, f, output_rate=AUDIO_RATE, cutoff_hz=8000),
                          AcarsDemodulator()) for f in freqs]
        self.sample_rate = int(sample_rate)
        self.on_message = on_message
        self.on_status = on_status or (lambda _msg: None)
        self._queue: queue.Queue = queue.Queue(maxsize=24)
        self._stop = threading.Event()
        self._thread = None
        self.dropped = 0
        self.iq_blocks = 0
        self.messages = 0
        self.last_error = ""

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="acars-demod")
        self._thread.start()
        self.on_status("ACARS: decodificando " + " / ".join(f"{f / 1e6:.3f}" for f, _c, _d in self.channels)
                       + " MHz (AM)")

    def feed(self, iq, center_hz: float, sample_rate: int):
        if self._stop.is_set() or int(sample_rate) != self.sample_rate:
            self.dropped += 1
            return
        try:
            self._queue.put_nowait((np.asarray(iq, dtype=np.complex64).copy(), float(center_hz)))
            self.iq_blocks += 1
        except queue.Full:
            self.dropped += 1

    def _loop(self):
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is None:
                break
            for freq, channel, demod in self.channels:
                try:
                    narrow = channel.channelize(*item)
                except ValueError as exc:      # frequência fora da banda capturada
                    self.last_error = f"{freq / 1e6:.3f} MHz: {exc}"
                    continue
                for msg in demod.process(np.abs(narrow)):
                    msg["freq_mhz"] = round(freq / 1e6, 3)
                    msg["timestamp"] = time.time()
                    self.messages += 1
                    self.on_message(msg)

    def diagnostics(self) -> dict:
        return {"iq_blocks": self.iq_blocks, "dropped": self.dropped,
                "messages": self.messages, "error": self.last_error}

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._thread = None
