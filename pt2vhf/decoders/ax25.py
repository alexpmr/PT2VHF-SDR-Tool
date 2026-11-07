"""AX.25: montagem/decodificação de quadros, CRC (FCS) e HDLC (bit stuffing)."""
from __future__ import annotations

from dataclasses import dataclass, field


def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


@dataclass
class AX25Frame:
    source: str
    dest: str
    path: list[str] = field(default_factory=list)
    info: bytes = b""
    control: int = 0x03
    pid: int = 0xF0

    def path_str(self) -> str:
        return ",".join(self.path)

    def tnc2(self) -> str:
        """Formato texto TNC2: FONTE>DEST,PATH:info"""
        hdr = f"{self.source}>{self.dest}"
        if self.path:
            hdr += "," + self.path_str()
        return hdr + ":" + self.info.decode("latin-1", errors="replace")


def _encode_addr(call: str, last: bool, h_bit: bool = False) -> bytes:
    call = call.upper()
    if call.endswith("*"):
        call, h_bit = call[:-1], True
    if "-" in call:
        base, ssid = call.split("-", 1)
        ssid = int(ssid)
    else:
        base, ssid = call, 0
    base = base[:6].ljust(6)
    out = bytes((ord(c) << 1) for c in base)
    last_byte = 0x60 | ((ssid & 0x0F) << 1) | (0x80 if h_bit else 0) | (0x01 if last else 0)
    return out + bytes([last_byte])


def _decode_addr(b: bytes) -> tuple[str, bool, bool]:
    call = "".join(chr(c >> 1) for c in b[:6]).strip()
    ssid = (b[6] >> 1) & 0x0F
    h = bool(b[6] & 0x80)
    last = bool(b[6] & 0x01)
    if ssid:
        call += f"-{ssid}"
    return call, h, last


def build_frame(frame: AX25Frame) -> bytes:
    """Quadro AX.25 UI completo com FCS (sem flags)."""
    addrs = [frame.dest, frame.source] + list(frame.path)
    body = b""
    for i, a in enumerate(addrs):
        body += _encode_addr(a, last=(i == len(addrs) - 1))
    body += bytes([frame.control, frame.pid]) + frame.info
    fcs = crc16_x25(body)
    return body + bytes([fcs & 0xFF, fcs >> 8])


def parse_frame(data: bytes) -> AX25Frame | None:
    """Valida FCS e decodifica. Retorna None se inválido."""
    if len(data) < 18:
        return None
    body, fcs = data[:-2], data[-2] | (data[-1] << 8)
    if crc16_x25(body) != fcs:
        return None
    addrs = []
    i = 0
    while True:
        if i + 7 > len(body):
            return None
        call, h, last = _decode_addr(body[i:i + 7])
        addrs.append((call, h))
        i += 7
        if last or len(addrs) >= 10:
            break
    if len(addrs) < 2 or i + 2 > len(body):
        return None
    dest, src = addrs[0][0], addrs[1][0]
    path = [c + ("*" if h else "") for c, h in addrs[2:]]
    control = body[i]
    pid = body[i + 1] if i + 1 < len(body) else 0
    return AX25Frame(src, dest, path, body[i + 2:], control, pid)


def hdlc_bits(frame_bytes: bytes, preamble_flags: int = 30, tail_flags: int = 3) -> list[int]:
    """Converte quadro em bits HDLC (LSB primeiro, bit stuffing, flags)."""
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    bits = flag * preamble_flags
    ones = 0
    for byte in frame_bytes:
        for k in range(8):
            b = (byte >> k) & 1
            bits.append(b)
            if b:
                ones += 1
                if ones == 5:
                    bits.append(0)
                    ones = 0
            else:
                ones = 0
    bits += flag * tail_flags
    return bits


def nrzi_encode(bits: list[int]) -> list[int]:
    """NRZI: bit 0 = transição, bit 1 = mantém."""
    level = 1
    out = []
    for b in bits:
        if b == 0:
            level ^= 1
        out.append(level)
    return out


class HDLCDeframer:
    """Recebe bits já decodificados de NRZI e extrai quadros entre flags."""

    def __init__(self, on_frame):
        self.on_frame = on_frame
        self._shift = 0
        self._ones = 0
        self._bits: list[int] = []
        self._in_frame = False

    def push(self, bit: int):
        self._shift = ((self._shift << 1) | bit) & 0xFF
        if self._shift == 0x7E:  # flag 01111110 (ordem de chegada)
            if self._in_frame and len(self._bits) >= 7 + 136:
                self._emit()
            self._in_frame = True
            self._bits = []
            self._ones = 0
            return
        if not self._in_frame:
            return
        if bit:
            self._ones += 1
            if self._ones > 6:  # abort
                self._in_frame = False
                self._bits = []
                return
            self._bits.append(1)
        else:
            if self._ones == 5:  # bit de stuffing: descarta
                self._ones = 0
                return
            self._ones = 0
            self._bits.append(0)
        if len(self._bits) > 8 * 400:
            self._in_frame = False
            self._bits = []

    def _emit(self):
        # os últimos 7 bits pertencem à flag (0111111) já acumulados
        bits = self._bits[:-7]
        if len(bits) % 8:
            return
        data = bytes(sum(bits[i + k] << k for k in range(8)) for i in range(0, len(bits), 8))
        frame = parse_frame(data)
        if frame is not None:
            self.on_frame(frame)
