"""AIS (161,975 / 162,025 MHz) a partir do IQ do SDR atual, via AIS-catcher embarcado.

O IQ já capturado é deslocado para 162,000 MHz no centro, reduzido para
288 kS/s e servido ao AIS-catcher (GPL-3.0, jvde-github) por um servidor
local no protocolo rtl_tcp (127.0.0.1, porta efêmera, CU8). Não se usa stdin
porque o AIS-catcher para Windows lê std::cin em modo texto, o que corromperia
o IQ. O AIS-catcher demodula os dois canais e devolve NMEA !AIVDM no stdout.
As sentenças são decodificadas pelo ``AISDecoder`` local. Um modo por vez:
o SDR precisa estar sintonizado perto de 162 MHz (o app faz isso ao iniciar).
Subprocesso sem shell, fora da thread de DSP, com fila limitada.
"""
from __future__ import annotations

import math
import os
import queue
import socket
import struct
import subprocess
import threading
import time

import numpy as np

from .sonde_rx import ChannelIQ, locate_binary
from .traffic import AISDecoder

AIS_CENTER_HZ = 162_000_000
AIS_CHANNELS_HZ = (161_975_000, 162_025_000)
AIS_RATE = 288_000
AIS_DIRNAME = "ais_catcher"
AIS_EXECUTABLE = "AIS-catcher"


def find_ais_catcher(supplied_path: str = "") -> tuple[str | None, str]:
    return locate_binary(AIS_EXECUTABLE, supplied_path, AIS_DIRNAME)


def build_ais_command(binary: str, port: int) -> list[str]:
    # -t: cliente rtl_tcp local; -s: taxa; -o 1: só NMEA no stdout.
    return [binary, "-t", "127.0.0.1", str(int(port)), "-s", str(AIS_RATE), "-o", "1"]


def to_cu8(samples: np.ndarray, scale: float) -> bytes:
    vals = np.stack((samples.real, samples.imag), axis=-1) * scale
    return np.clip(np.round(vals * 127.5 + 127.5), 0, 255).astype(np.uint8).tobytes()


class LocalIQServer:
    """Servidor rtl_tcp mínimo só em 127.0.0.1 para um único cliente (AIS-catcher).

    Envia o cabeçalho ``RTL0`` e o IQ CU8; os comandos recebidos (frequência,
    ganho, taxa) são lidos e ignorados, pois a sintonia é do próprio app.
    """

    def __init__(self, timeout: float = 15.0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.sock.settimeout(timeout)
        self.port = self.sock.getsockname()[1]
        self.conn = None

    def accept(self):
        conn, addr = self.sock.accept()
        if addr[0] != "127.0.0.1":
            conn.close()
            raise OSError("conexão recusada: origem não local")
        conn.sendall(b"RTL0" + struct.pack(">II", 5, 29))   # R820T, 29 ganhos
        threading.Thread(target=self._drain, args=(conn,), daemon=True, name="ais-rtltcp-cmd").start()
        self.conn = conn
        return conn

    @staticmethod
    def _drain(conn):
        try:
            while conn.recv(256):
                pass
        except OSError:
            return

    def send(self, data: bytes):
        if self.conn is not None:
            self.conn.sendall(data)

    def close(self):
        for s in (self.conn, self.sock):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
        self.conn = None


class AISReceiver:
    """Encaminha o IQ do SDR ao AIS-catcher e entrega posições AIS (Track)."""

    def __init__(self, sample_rate: int, on_track, on_status=None, binary_path: str = ""):
        self.channel = ChannelIQ(sample_rate, AIS_CENTER_HZ, output_rate=AIS_RATE,
                                 cutoff_hz=AIS_RATE * 0.4)
        self.on_track = on_track
        self.on_status = on_status or (lambda _msg: None)
        self.binary_path = binary_path
        self.decoder = AISDecoder()
        self.proc = None
        self.server = None
        self._level = 0.0
        self._queue: queue.Queue = queue.Queue(maxsize=24)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.dropped = 0
        self.iq_blocks = 0
        self.sentences = 0
        self.positions = 0
        self.last_error = ""

    def start(self):
        binary, origin = find_ais_catcher(self.binary_path)
        if not binary:
            raise FileNotFoundError(
                "AIS-catcher indisponível (cópia embarcada ausente). Reinstale o PT2VHF SDR Tool.")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.server = LocalIQServer()
        self.proc = subprocess.Popen(build_ais_command(binary, self.server.port),
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=flags, bufsize=0)
        self._stop.clear()
        for target, name in ((self._write_loop, "ais-iq-writer"), (self._read_loop, "ais-nmea-reader"),
                             (self._stderr_loop, "ais-stderr")):
            t = threading.Thread(target=target, daemon=True, name=name)
            t.start()
            self._threads.append(t)
        self.on_status(f"AIS: AIS-catcher ({origin}) iniciado; aguardando navios em 161,975/162,025 MHz")

    def feed(self, iq, center_hz: float, sample_rate: int):
        """Thread DSP: apenas copia o bloco para a fila limitada."""
        if self._stop.is_set() or int(sample_rate) != self.channel.sample_rate:
            self.dropped += 1
            return
        try:
            self._queue.put_nowait((np.asarray(iq, dtype=np.complex64).copy(), float(center_hz)))
            self.iq_blocks += 1
        except queue.Full:
            self.dropped += 1

    def _write_loop(self):
        try:
            self.server.accept()
            while not self._stop.is_set():
                try:
                    item = self._queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if item is None:
                    break
                narrow = self.channel.channelize(*item)
                if narrow.size:
                    peak = float(np.percentile(np.abs(narrow), 99)) + 1e-9
                    self._level = peak if not self._level else 0.9 * self._level + 0.1 * peak
                    self.server.send(to_cu8(narrow, 0.7 / self._level))
                if self.proc and self.proc.poll() is not None:
                    raise RuntimeError(f"AIS-catcher encerrou com código {self.proc.returncode}")
        except (OSError, ValueError, RuntimeError) as exc:
            if not self._stop.is_set():
                self.last_error = str(exc)
                self.on_status(f"AIS: erro no pipeline: {exc}")
        finally:
            if self.server:
                self.server.close()

    def _read_loop(self):
        if not self.proc or not self.proc.stdout:
            return
        try:
            for raw in self.proc.stdout:
                if self._stop.is_set():
                    break
                line = raw.decode("ascii", errors="replace").strip()
                if not line.startswith("!"):
                    continue
                self.sentences += 1
                track = self.decoder.ingest(line, time.time())
                if track is not None:
                    self.positions += 1
                    self.on_track(track)
        except OSError as exc:
            if not self._stop.is_set():
                self.last_error = str(exc)

    def _stderr_loop(self):
        if not self.proc or not self.proc.stderr:
            return
        try:
            for raw in self.proc.stderr:
                msg = raw.decode("utf-8", errors="replace").strip()[-300:]
                if msg and ("error" in msg.lower() or "erro" in msg.lower()):
                    self.last_error = msg
                    self.on_status(f"AIS: {msg}")
        except OSError:
            return

    def diagnostics(self) -> dict:
        return {"iq_blocks": self.iq_blocks, "dropped": self.dropped,
                "sentences": self.sentences, "positions": self.positions,
                "alive": self.proc is not None and self.proc.poll() is None,
                "error": self.last_error}

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        proc = self.proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        for t in self._threads:
            if t.is_alive() and t is not threading.current_thread():
                t.join(timeout=1)
        self._threads.clear()
        if self.server:
            self.server.close()
        self.proc = None
        self.server = None


# ----------------------------------------------------------------- sinal sintético
def _crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


def ais_position_bits(mmsi: int, lat: float, lon: float, sog_kn: float = 0.0,
                      cog_deg: float = 0.0) -> str:
    """Mensagem AIS tipo 1 (168 bits) para testes."""
    def field(value, width):
        return format(value & ((1 << width) - 1), f"0{width}b")
    return (field(1, 6) + field(0, 2) + field(mmsi, 30) + field(0, 4) + field(-128, 8)
            + field(round(sog_kn * 10), 10) + field(0, 1) + field(round(lon * 600000), 28)
            + field(round(lat * 600000), 27) + field(round(cog_deg * 10), 12) + field(511, 9)
            + field(60, 6) + field(0, 2) + field(0, 3) + field(0, 1) + field(0, 19))


def ais_frame_bits(payload_bits: str) -> np.ndarray:
    """HDLC (bytes LSB primeiro, CRC X.25, bit stuffing, flags) + NRZI."""
    data = bytes(int(payload_bits[i:i + 8], 2) for i in range(0, len(payload_bits), 8))
    crc = _crc16_x25(data)
    raw = []
    for byte in data + bytes((crc & 0xFF, crc >> 8)):
        raw += [(byte >> k) & 1 for k in range(8)]
    stuffed, ones = [], 0
    for bit in raw:
        stuffed.append(bit)
        ones = ones + 1 if bit else 0
        if ones == 5:
            stuffed.append(0)
            ones = 0
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    bits = [0, 1] * 12 + flag + stuffed + flag + [0] * 8
    level, out = 1, []
    for bit in bits:
        if bit == 0:
            level ^= 1
        out.append(level)
    return np.array(out, dtype=np.int8)


def synth_ais_iq(payloads, sample_rate: int = 2_400_000, center_hz: float = 162_300_000,
                 channel_hz: float = AIS_CHANNELS_HZ[0], gap_s: float = 0.05,
                 snr_db: float = 25.0, seed: int = 0) -> np.ndarray:
    """IQ GMSK 9600 Bd (BT 0,4, h=0,5) de mensagens AIS, para testes/autoteste."""
    baud, sps = 9600, sample_rate / 9600
    rng = np.random.default_rng(seed)
    gap = np.zeros(int(gap_s * sample_rate))
    parts = [gap]
    for payload in payloads:
        levels = ais_frame_bits(payload)
        n = int(len(levels) * sps)
        idx = np.minimum((np.arange(n) / sps).astype(np.int64), len(levels) - 1)
        parts.append((levels[idx] * 2 - 1).astype(np.float64))
        parts.append(gap)
    nrz = np.concatenate(parts)
    on = np.concatenate([np.zeros_like(p) if p is gap else np.ones_like(p) for p in parts])
    t = np.arange(-2 * sps, 2 * sps + 1) / sps
    g = np.exp(-2 * (math.pi * 0.4 * t) ** 2 / math.log(2))
    nrz = np.convolve(nrz, g / g.sum(), mode="same")
    freq = (channel_hz - center_hz) + (baud / 4) * nrz
    phase = 2 * math.pi * np.cumsum(freq) / sample_rate
    sig = 0.5 * on * np.exp(1j * phase)
    noise = 0.5 * 10 ** (-snr_db / 20) / math.sqrt(2)
    sig = sig + noise * (rng.standard_normal(sig.size) + 1j * rng.standard_normal(sig.size))
    return sig.astype(np.complex64)


def synthetic_ais_check(binary: str | None = None, timeout: float = 60.0) -> list:
    """IQ AIS sintético -> canal 288 kS/s -> AIS-catcher -> NMEA -> Track (sem RF real)."""
    binary = binary or find_ais_catcher()[0]
    if not binary:
        raise FileNotFoundError("AIS-catcher não encontrado")
    rate, center = 2_400_000, 162_300_000
    payloads = [ais_position_bits(710000001 + k, -23.0 - 0.01 * k, -43.2, 12.3, 45.6) for k in range(3)]
    iq = synth_ais_iq(payloads * 2, rate, center)
    channel = ChannelIQ(rate, AIS_CENTER_HZ, output_rate=AIS_RATE, cutoff_hz=AIS_RATE * 0.4)
    narrow = np.concatenate([channel.channelize(iq[i:i + 65536], center)
                             for i in range(0, len(iq), 65536)])
    data = to_cu8(narrow, 0.7 / (float(np.percentile(np.abs(narrow), 99)) + 1e-9))
    data += bytes([127, 127]) * (AIS_RATE // 2)   # 0,5 s de silêncio para esvaziar
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    server = LocalIQServer(timeout=timeout)
    proc = subprocess.Popen(build_ais_command(binary, server.port), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)
    lines: list[bytes] = []
    reader = threading.Thread(target=lambda: lines.extend(proc.stdout), daemon=True)
    reader.start()
    decoder = AISDecoder()
    try:
        server.accept()
        for i in range(0, len(data), 65536):
            server.send(data[i:i + 65536])
        deadline = time.time() + 5
        while time.time() < deadline:
            time.sleep(0.2)
            for line in list(lines):
                decoder.ingest(line.decode("ascii", errors="replace").strip(), 0.0)
            if len(decoder.tracks) >= 3:
                break
    finally:
        server.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    return list(decoder.tracks.values())
