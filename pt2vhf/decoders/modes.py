"""ADS-B (Mode S DF17/DF18, 1090 MHz) decodificado nativamente do IQ do SDR.

Implementação própria em NumPy, sem programas externos: detecção de preâmbulo
na magnitude do IQ, demodulação PPM (1 Mbit/s) por interpolação fracionária
(2,4 ou 2,88 MS/s), CRC-24 com correção de 1 bit e decodificação de identificação,
posição CPR global (par par/ímpar), altitude barométrica e velocidade.

Limitações conhecidas: corrige no máximo 1 bit por quadro, sem DF4/5/20/21 (paridade
sobreposta ao endereço) e sem altitude Gillham. Precisa do SDR sintonizado em
1090 MHz com taxa >= 2,4 MS/s; um modo por vez (o SDR sai da faixa anterior).
"""
from __future__ import annotations

import math
import queue
import threading
import time

import numpy as np

ADSB_FREQ_HZ = 1_090_000_000
MIN_SAMPLE_RATE = 2_400_000  # >= 2,4 MS/s: 1,2 amostra por meio-µs
_PREAMBLE_US = (0.0, 1.0, 3.5, 4.5)
_QUIET_US = (2.0, 2.5, 5.5, 6.0, 6.5, 7.0)
_LONG_BITS = 112
_SHORT_BITS = 56
_CHARSET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ##### ###############0123456789######"


def _crc_table():
    poly = 0xFFF409
    table = []
    for byte in range(256):
        crc = byte << 16
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if crc & 0x800000 else (crc << 1)
        table.append(crc & 0xFFFFFF)
    return table


_CRC_TABLE = _crc_table()


def crc24(data: bytes) -> int:
    """Resto CRC-24 Mode S (polinômio 0xFFF409) sobre todos os bytes."""
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFF) ^ _CRC_TABLE[((crc >> 16) ^ byte) & 0xFF]
    return crc


def residual(msg: bytes) -> int:
    """0 para mensagens DF17/DF18 íntegras (dados + paridade)."""
    return crc24(msg[:-3]) ^ int.from_bytes(msg[-3:], "big")


def _single_bit_syndromes():
    table = {}
    for pos in range(5, _LONG_BITS):           # não corrige o campo DF
        err = bytearray(_LONG_BITS // 8)
        err[pos // 8] = 0x80 >> (pos % 8)
        table[residual(bytes(err))] = pos
    return table


_SYNDROMES = _single_bit_syndromes()


def correct_single_bit(msg: bytes) -> bytes | None:
    """Mensagem DF17/18 íntegra, corrigindo até 1 bit; None se irrecuperável."""
    syn = residual(msg)
    if syn == 0:
        return msg
    pos = _SYNDROMES.get(syn)
    if pos is None:
        return None
    fixed = bytearray(msg)
    fixed[pos // 8] ^= 0x80 >> (pos % 8)
    return bytes(fixed)


class ModeSDemodulator:
    """Extrai quadros Mode S íntegros (DF17/DF18) de blocos IQ contínuos."""

    def __init__(self, sample_rate: int, max_candidates: int = 4000):
        if sample_rate < MIN_SAMPLE_RATE:
            raise ValueError("ADS-B requer taxa de amostragem >= 2,4 MS/s")
        self.sample_rate = int(sample_rate)
        self.sps = self.sample_rate / 1e6          # amostras por microssegundo
        self.max_candidates = max_candidates
        self._span = int(math.ceil((8 + _LONG_BITS + 1) * self.sps)) + 4
        self._tail = np.empty(0, dtype=np.float32)
        self.frames = 0
        self.candidates = 0
        self.crc_errors = 0
        self.corrected = 0

    def process(self, iq) -> list[bytes]:
        mag = np.abs(np.asarray(iq, dtype=np.complex64).reshape(-1)).astype(np.float32)
        data = np.concatenate((self._tail, mag))
        if data.size < self._span + 10:
            self._tail = data
            return []
        # Integral exata da magnitude em janelas fracionárias de 0,5 µs.
        cum = np.concatenate(([0.0], np.cumsum(data, dtype=np.float64)))
        limit = data.size - self._span
        half = 0.5 * self.sps

        def window(t_us):
            def at(offset):
                whole = int(math.floor(offset))
                frac = offset - whole
                return cum[whole:whole + limit] * (1 - frac) + cum[whole + 1:whole + 1 + limit] * frac
            start = t_us * self.sps
            return at(start + half) - at(start)

        pulse = [window(t) for t in _PREAMBLE_US]
        quiet = np.mean([window(t) for t in _QUIET_US], axis=0)
        low_pulse = np.minimum.reduce(pulse)
        noise = float(np.median(quiet)) + 1e-12
        cand = np.flatnonzero((low_pulse > 1.7 * quiet) & (low_pulse > 2.0 * noise))
        if cand.size > self.max_candidates:
            order = np.argsort(low_pulse[cand])[::-1][:self.max_candidates]
            cand = np.sort(cand[order])
        self.candidates += int(cand.size)
        found = []
        next_free = -1
        for start in cand:
            if start < next_free:
                continue
            msg = self._decode_at(cum, int(start))
            if msg is not None:
                found.append(msg)
                next_free = start + int((8 + len(msg) * 8) * self.sps)
        self._tail = data[limit:].copy()
        self.frames += len(found)
        return found

    def _decode_at(self, cum, start: int):
        bits_idx = np.arange(_LONG_BITS)
        grid = np.arange(cum.size)
        half = 0.5 * self.sps
        for shift in (0.0, -0.25, 0.25, -0.5, 0.5, -0.75, 0.75):
            edges = start + shift + (8.0 + bits_idx) * self.sps
            c0, c1, c2 = (np.interp(edges + k * half, grid, cum) for k in (0, 1, 2))
            bits = ((c1 - c0) > (c2 - c1)).astype(np.uint8)
            df = int(bits[0]) << 4 | int(bits[1]) << 3 | int(bits[2]) << 2 | int(bits[3]) << 1 | int(bits[4])
            if df not in (17, 18):
                continue
            msg = correct_single_bit(np.packbits(bits).tobytes())
            if msg is not None:
                self.corrected += int(msg != np.packbits(bits).tobytes())
                return msg
        self.crc_errors += 1
        return None


def _bits(msg: bytes) -> str:
    return "".join(f"{b:08b}" for b in msg)


def _nl(lat: float) -> int:
    if abs(lat) >= 87.0:
        return 1 if abs(lat) > 87.0 else 2
    if lat == 0:
        return 59
    a = 1 - math.cos(math.pi / 30)
    b = math.cos(math.pi / 180 * abs(lat)) ** 2
    return int(math.floor(2 * math.pi / math.acos(1 - a / b)))


def cpr_global(even: tuple[int, int], odd: tuple[int, int], newest_odd: bool):
    """Decodificação CPR global de um par par/ímpar (valores brutos de 17 bits)."""
    lat_e, lon_e = even[0] / 131072, even[1] / 131072
    lat_o, lon_o = odd[0] / 131072, odd[1] / 131072
    j = math.floor(59 * lat_e - 60 * lat_o + 0.5)
    rlat_e = 360 / 60 * ((j % 60) + lat_e)
    rlat_o = 360 / 59 * ((j % 59) + lat_o)
    rlat_e -= 360 if rlat_e >= 270 else 0
    rlat_o -= 360 if rlat_o >= 270 else 0
    if _nl(rlat_e) != _nl(rlat_o):
        return None
    lat = rlat_o if newest_odd else rlat_e
    nl = _nl(lat)
    m = math.floor(lon_e * (nl - 1) - lon_o * nl + 0.5)
    ni = max(nl - (1 if newest_odd else 0), 1)
    lon = 360 / ni * ((m % ni) + (lon_o if newest_odd else lon_e))
    lon -= 360 if lon >= 180 else 0
    if not (-90 <= lat <= 90):
        return None
    return lat, lon


class ADSBDecoder:
    """Mantém o estado por aeronave e gera entradas no formato aircraft.json."""

    def __init__(self, pair_window_s: float = 10.0):
        self.aircraft: dict[str, dict] = {}
        self.pair_window_s = pair_window_s
        self.messages = 0

    def ingest(self, msg: bytes, now: float | None = None) -> dict | None:
        now = time.time() if now is None else now
        if len(msg) != 14 or residual(msg) != 0:
            return None
        bits = _bits(msg)
        if int(bits[0:5], 2) not in (17, 18):
            return None
        self.messages += 1
        icao = msg[1:4].hex().upper()
        me = bits[32:88]
        tc = int(me[0:5], 2)
        ac = self.aircraft.setdefault(icao, {"hex": icao, "messages": 0})
        ac["messages"] += 1
        ac["seen"] = now
        if 1 <= tc <= 4:
            name = "".join(_CHARSET[int(me[8 + 6 * i:14 + 6 * i], 2)] for i in range(8))
            ac["flight"] = name.replace("#", "").strip()
        elif 9 <= tc <= 18 or 20 <= tc <= 22:
            alt_bits = me[8:20]
            if 9 <= tc <= 18 and alt_bits[7] == "1":
                n = int(alt_bits[:7] + alt_bits[8:], 2)
                ac["alt_baro"] = n * 25 - 1000
            elif 20 <= tc <= 22:
                ac["alt_geom"] = round(int(alt_bits, 2) * 3.28084)
            odd = me[21] == "1"
            raw = (int(me[22:39], 2), int(me[39:56], 2))
            ac["cpr_odd" if odd else "cpr_even"] = (raw, now)
            even_pair, odd_pair = ac.get("cpr_even"), ac.get("cpr_odd")
            if even_pair and odd_pair and abs(even_pair[1] - odd_pair[1]) <= self.pair_window_s:
                pos = cpr_global(even_pair[0], odd_pair[0], newest_odd=odd)
                if pos is not None:
                    ac["lat"], ac["lon"] = round(pos[0], 5), round(pos[1], 5)
                    ac["seen_pos_time"] = now
        elif tc == 19:
            subtype = int(me[5:8], 2)
            if subtype in (1, 2):
                factor = 4 if subtype == 2 else 1
                v_ew, v_ns = int(me[14:24], 2), int(me[25:35], 2)
                if v_ew and v_ns:
                    vx = (v_ew - 1) * factor * (-1 if me[13] == "1" else 1)
                    vy = (v_ns - 1) * factor * (-1 if me[24] == "1" else 1)
                    ac["gs"] = round(math.hypot(vx, vy), 1)
                    ac["track"] = round(math.degrees(math.atan2(vx, vy)) % 360, 1)
                vr = int(me[37:46], 2)
                if vr:
                    ac["baro_rate"] = (vr - 1) * 64 * (-1 if me[36] == "1" else 1)
        return self.snapshot_entry(icao, now)

    def snapshot_entry(self, icao: str, now: float) -> dict:
        ac = self.aircraft[icao]
        entry = {k: v for k, v in ac.items() if not k.startswith("cpr_") and k != "seen_pos_time"}
        if "seen_pos_time" in ac:
            entry["seen_pos"] = round(now - ac["seen_pos_time"], 1)
        return entry

    def snapshot(self, now: float | None = None, max_age_s: float = 120.0) -> dict:
        """Objeto compatível com aircraft.json (readsb/dump1090) para parse_adsb."""
        now = time.time() if now is None else now
        for icao in [k for k, v in self.aircraft.items() if now - v.get("seen", 0) > max_age_s]:
            del self.aircraft[icao]
        return {"now": now, "messages": self.messages,
                "aircraft": [self.snapshot_entry(k, now) for k in self.aircraft]}


class ADSBReceiver:
    """Demodula ADS-B numa thread própria a partir do IQ do SDR (fila limitada)."""

    def __init__(self, sample_rate: int, on_update, on_status=None):
        self.demod = ModeSDemodulator(sample_rate)
        self.decoder = ADSBDecoder()
        self.sample_rate = int(sample_rate)
        self.on_update = on_update          # recebe snapshot aircraft.json (dict)
        self.on_status = on_status or (lambda _msg: None)
        self._queue: queue.Queue = queue.Queue(maxsize=16)
        self._stop = threading.Event()
        self._thread = None
        self.dropped = 0
        self.iq_blocks = 0
        self.last_error = ""
        self._last_push = 0.0

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="adsb-demod")
        self._thread.start()
        self.on_status(f"ADS-B: demodulando 1090 MHz a {self.sample_rate / 1e6:g} MS/s")

    def feed(self, iq, center_hz: float, sample_rate: int):
        if self._stop.is_set() or int(sample_rate) != self.sample_rate:
            self.dropped += 1
            return
        if abs(center_hz - ADSB_FREQ_HZ) > sample_rate * 0.3:
            self.last_error = "SDR fora de 1090 MHz"
            self.dropped += 1
            return
        try:
            self._queue.put_nowait(np.asarray(iq, dtype=np.complex64).copy())
            self.iq_blocks += 1
        except queue.Full:
            self.dropped += 1

    def _loop(self):
        while not self._stop.is_set():
            try:
                block = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if block is None:
                break
            now = time.time()
            changed = False
            for msg in self.demod.process(block):
                changed |= self.decoder.ingest(msg, now) is not None
            if changed and now - self._last_push >= 1.0:
                self._last_push = now
                self.on_update(self.decoder.snapshot(now))

    def diagnostics(self) -> dict:
        return {"iq_blocks": self.iq_blocks, "dropped": self.dropped,
                "frames": self.demod.frames, "corrected": self.demod.corrected,
                "aircraft": len(self.decoder.aircraft), "error": self.last_error}

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._thread = None


def synth_adsb_iq(messages, sample_rate: int = 2_400_000, gap_us: float = 300.0,
                  snr_db: float = 20.0, freq_offset_hz: float = 0.0, seed: int = 0) -> np.ndarray:
    """IQ sintético PPM de quadros Mode S (para testes/autoteste, não homologação)."""
    over = 10
    hi_rate = sample_rate * over
    chunks = []
    gap = np.zeros(int(gap_us * hi_rate / 1e6))
    for msg in messages:
        chunks.append(gap)
        chips = [1, 0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0]  # preâmbulo em meio-µs
        for bit in _bits(msg):
            chips += [1, 0] if bit == "1" else [0, 1]
        half = hi_rate / 2e6
        n = int(len(chips) * half)
        wave = np.zeros(n)
        for k, chip in enumerate(chips):
            if chip:
                wave[int(k * half):int((k + 1) * half)] = 1.0
        chunks.append(wave)
    chunks.append(gap)
    env = np.concatenate(chunks)
    env = env[:len(env) // over * over].reshape(-1, over).mean(axis=1)
    rng = np.random.default_rng(seed)
    t = np.arange(env.size) / sample_rate
    sig = 0.5 * env * np.exp(1j * (2 * math.pi * freq_offset_hz * t + rng.uniform(0, 2 * math.pi)))
    noise = 0.5 * 10 ** (-snr_db / 20) / math.sqrt(2)
    sig = sig + noise * (rng.standard_normal(env.size) + 1j * rng.standard_normal(env.size))
    return sig.astype(np.complex64)
