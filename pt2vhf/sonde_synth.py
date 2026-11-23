"""Quadro RS41 sintético (GFSK 4800 Bd) para autoteste do pipeline embarcado.

Gera somente sinal de teste determinístico: prova que IQ -> fsk_demod ->
rs41mod -> JSON funciona no executável empacotado (pipes binários, argumentos,
CRC). NÃO substitui captura IQ real de radiossonda (homologação RF).
"""
from __future__ import annotations

import math
import struct

import numpy as np

HEADER = bytes((0x86, 0x35, 0xF4, 0x40, 0x93, 0xDF, 0x1A, 0x60))
MASK = bytes((
    0x96, 0x83, 0x3E, 0x51, 0xB1, 0x49, 0x08, 0x98, 0x32, 0x05, 0x59, 0x0E, 0xF9, 0x44, 0xC6, 0x26,
    0x21, 0x60, 0xC2, 0xEA, 0x79, 0x5D, 0x6D, 0xA1, 0x54, 0x69, 0x47, 0x0C, 0xDC, 0xE8, 0x5C, 0xF1,
    0xF7, 0x76, 0x82, 0x7F, 0x07, 0x99, 0xA2, 0x2C, 0x93, 0x7C, 0x30, 0x63, 0xF5, 0x10, 0x2E, 0x61,
    0xD0, 0xBC, 0xB4, 0xB6, 0x06, 0xAA, 0xF4, 0x23, 0x78, 0x6E, 0x3B, 0xAE, 0xBF, 0x7B, 0x4C, 0xC1))
FRAME_LEN = 320
BAUD = 4800
DEVIATION_HZ = 2400


def crc16(data: bytes) -> int:
    rem = 0xFFFF
    for byte in data:
        rem ^= byte << 8
        for _ in range(8):
            rem = ((rem << 1) ^ 0x1021) if rem & 0x8000 else (rem << 1)
            rem &= 0xFFFF
    return rem


def _gf_tables():
    exp, log = [0] * 512, [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_EXP, _LOG = _gf_tables()


def _gmul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(nsym: int = 24):
    g = [1]                                  # coeficientes, índice = potência de X
    for i in range(nsym):
        root = _EXP[i]                       # (X - alpha^i), b = 0
        nxt = [0] * (len(g) + 1)
        for k, c in enumerate(g):
            nxt[k] ^= _gmul(c, root)
            nxt[k + 1] ^= c
        g = nxt
    return g


_GEN = _rs_generator()


def rs_parity(message) -> bytes:
    """RS(255,231) sistemático como em rs41mod: cw[0:24] paridade, cw[24:] mensagem."""
    cw = [0] * 24 + list(message) + [0] * (231 - len(message))
    rem = cw[:]
    for deg in range(254, 23, -1):          # divisão por g(X), mônico de grau 24
        coef = rem[deg]
        if coef:
            for k, gk in enumerate(_GEN):
                rem[deg - 24 + k] ^= _gmul(coef, gk)
    return bytes(rem[:24])


def _block(pck_id: int, payload: bytes) -> bytes:
    body = bytes((pck_id, len(payload))) + payload
    return body + struct.pack("<H", crc16(payload))


def _ecef(lat: float, lon: float, alt: float):
    a, f = 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    phi, lam = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    return ((n + alt) * math.cos(phi) * math.cos(lam),
            (n + alt) * math.cos(phi) * math.sin(lam),
            (n * (1 - e2) + alt) * math.sin(phi))


def rs41_frame(serial: str = "T1234567", frame_nb: int = 1000, lat: float = -23.5,
               lon: float = -46.6, alt: float = 12000.0, week: int = 2400,
               tow_ms: int = 300_000_000) -> bytes:
    """Quadro RS41 padrão (320 bytes, não embaralhado) com CRCs válidos."""
    sid = serial.encode("ascii")[:8].ljust(8, b"0")
    frame = bytearray(FRAME_LEN)
    frame[0:8] = HEADER
    frame[0x38] = 0x0F                      # tipo: quadro padrão sem AUX
    status = bytearray(0x28)
    status[0:2] = struct.pack("<H", frame_nb)
    status[2:10] = sid
    status[10] = 28                         # bateria 2,8 V (0x045)
    gps1 = bytearray(0x1E)
    gps1[0:2] = struct.pack("<H", week)
    gps1[2:6] = struct.pack("<i", tow_ms)
    gps3 = bytearray(0x15)
    x, y, z = _ecef(lat, lon, alt)
    gps3[0:12] = struct.pack("<iii", round(x * 100), round(y * 100), round(z * 100))
    gps3[18] = 9                            # satélites
    blocks = (_block(0x79, bytes(status)) + _block(0x7A, bytes(0x2A))
              + _block(0x7C, bytes(gps1)) + _block(0x7D, bytes(0x59))
              + _block(0x7B, bytes(gps3)) + _block(0x76, bytes(0x11)))
    frame[0x39:0x39 + len(blocks)] = blocks
    assert len(frame) == FRAME_LEN and 0x39 + len(blocks) == FRAME_LEN
    msg = frame[56:]
    frame[8:32] = rs_parity(msg[0::2])
    frame[32:56] = rs_parity(msg[1::2])
    return bytes(frame)


def rs41_bits(frames) -> np.ndarray:
    """Bits transmitidos (embaralhados, LSB primeiro), um quadro por segundo.

    Como a RS41 real, cada quadro de 2560 bits ocupa um período de 4800 bits;
    o restante é preenchido com bits alternados.
    """
    out = [np.tile([0, 1], BAUD // 2)]     # 1 s de aquisição do demodulador
    for raw in frames:
        out.append(np.tile([0, 1], (BAUD - FRAME_LEN * 8) // 2))
        xored = bytes(b ^ MASK[i % len(MASK)] for i, b in enumerate(raw))
        out.append(np.unpackbits(np.frombuffer(xored, dtype=np.uint8), bitorder="little"))
    out.append(np.tile([0, 1], BAUD // 2))  # rs41mod lê adiante até 518 bytes
    return np.concatenate(out).astype(np.int8)


def rs41_iq(frames, sample_rate: int = 240_000, offset_hz: float = 0.0,
            snr_db: float = 25.0, seed: int = 0) -> np.ndarray:
    """IQ complex64 GFSK (BT 0,5) de quadros RS41 em offset_hz do centro."""
    bits = rs41_bits(frames)
    sps = sample_rate / BAUD
    n = int(len(bits) * sps)
    idx = np.minimum((np.arange(n) / sps).astype(np.int64), len(bits) - 1)
    nrz = (bits[idx] * 2 - 1).astype(np.float64)
    # Filtro gaussiano BT=0,5
    t = np.arange(-2 * sps, 2 * sps + 1) / sps
    bt = 0.5
    g = np.exp(-2 * (math.pi * bt * t) ** 2 / math.log(2))
    nrz = np.convolve(nrz, g / g.sum(), mode="same")
    freq = offset_hz + DEVIATION_HZ * nrz
    phase = 2 * math.pi * np.cumsum(freq) / sample_rate
    sig = 0.5 * np.exp(1j * phase)
    rng = np.random.default_rng(seed)
    noise_amp = 0.5 / math.sqrt(2) * 10 ** (-snr_db / 20)
    sig = sig + noise_amp * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    return sig.astype(np.complex64)
