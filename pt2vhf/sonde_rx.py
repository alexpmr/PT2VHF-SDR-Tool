"""Receptor RS41 por amostras IQ do *mesmo* SDR usado no waterfall.

DSP próprio: deslocamento complexo para FI +12 kHz e decimação a 48 kS/s.
Decodificação FSK/FEC/telemetria por fsk_demod e rs41mod (projeto auto_rx,
binários externos de código aberto, não distribuídos no instalador).
Executa subprocessos sem shell, fora da thread de recepção; desativado por padrão.
"""
from __future__ import annotations

import math
import os
import queue
import shutil
import subprocess
import threading
import time
import json
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly
from .traffic import parse_radiosondes

OUTPUT_RATE = 48000
SIGNAL_OFFSET_HZ = 12000


def find_binary(executable: str, supplied_path: str = "") -> str:
    """Sem download automático ou execução de scripts; só .exe/binário do usuário ou PATH."""
    name = supplied_path.strip() or executable
    if not name:
        raise ValueError("Nome vazio do decodificador")
    located = shutil.which(name)
    if not located:
        raise FileNotFoundError(
            f"{executable} indisponível. Instale os demoduladores do projeto radiosonde_auto_rx "
            f"e indique o executável em Configurações (ou adicione ao PATH).")
    return located


def build_decoder_commands(freq_hz: float, fsk_binary: str, rs41_binary: str):
    if not math.isfinite(freq_hz) or not 400e6 <= freq_hz <= 406e6:
        raise ValueError("A recepção RS41 configurada suporta a faixa 400–406 MHz")
    demod = [fsk_binary, "--cs16", "-b", "1200", "-u", "22800",
             "-s", "--mask", "5000", "--nsym=300", "-p", "5",
             "2", "48000", "4800", "-", "-"]
    decoder = [rs41_binary, "--ptu2", "--json", "--softin", "-i",
               "--jsn_cfq", str(int(round(freq_hz)))]
    return demod, decoder


class ChannelIQ:
    """Canal complexo centrado 12 kHz ABAIXO da portadora, saída IQ int16 48 kHz.

    Uma fase contínua é mantida entre blocos. Cada bloco é reamostrado com
    resample_poly; blocos grandes de SDR fornecem margem de filtro na entrada.
    """
    def __init__(self, sample_rate: int, station_hz: float):
        self.sample_rate = int(sample_rate)
        self.station_hz = float(station_hz)
        self.samples = 0
        self._center = None
        self._tail = np.empty(0, dtype=np.complex64)
        if self.sample_rate < 96000:
            raise ValueError("IQ com taxa inferior a 96 kS/s")
        self._gcd = math.gcd(self.sample_rate, OUTPUT_RATE)
        self._up, self._down = OUTPUT_RATE // self._gcd, self.sample_rate // self._gcd

    def convert(self, block, center_hz: float) -> bytes:
        samples = np.asarray(block, dtype=np.complex64).reshape(-1)
        if samples.size == 0:
            return b""
        center_hz = float(center_hz)
        off = self.station_hz - SIGNAL_OFFSET_HZ - center_hz
        if abs(off) >= self.sample_rate / 2 - 30000:
            raise ValueError("Frequência da sonda fora da banda IQ capturada")
        if self._center != center_hz:
            self._center = center_hz
            self.samples = 0
            self._tail = np.empty(0, dtype=np.complex64)
        position = np.arange(samples.size, dtype=np.float64) + self.samples
        self.samples += samples.size
        translated = (samples * np.exp(-2j * math.pi * off / self.sample_rate * position)).astype(np.complex64)
        # FIR com overlap para reduzir transientes nos limites dos blocos.
        prefix = self._tail
        n_prefix_out = math.ceil(len(prefix) * self._up / self._down)
        joined = np.concatenate((prefix, translated))
        narrow = resample_poly(joined, self._up, self._down)
        # Compensa o atraso do trecho anexado, sem introduzir lacunas longas.
        narrow = narrow[n_prefix_out:]
        self._tail = joined[-min(len(joined), 10 * self._down):].copy()
        # O fsk_demod espera I/Q signed 16 bit little-endian, intercalado.
        vals = np.stack((narrow.real, narrow.imag), axis=-1)
        ints = np.round(np.clip(vals, -1, 1) * 30000).astype("<i2")
        return ints.tobytes()


class RS41Receiver:
    """Encaminha amostras já capturadas ao fsk_demod e rs41mod, sem outro dongle."""

    def __init__(self, sample_rate: int, station_hz: float, on_decoded, on_status=None,
                 fsk_path="", decoder_path=""):
        self.channel = ChannelIQ(sample_rate, station_hz)
        self.on_decoded = on_decoded
        self.on_status = on_status or (lambda _: None)
        self.fsk_path = fsk_path
        self.decoder_path = decoder_path
        self._queue = queue.Queue(maxsize=12)
        self._stop = threading.Event()
        self._writer = None
        self._reader = None
        self.demod = None
        self.decoder = None
        self.dropped = 0
        self.received = 0
        self._startup_error = None

    def start(self):
        fsk = find_binary("fsk_demod", self.fsk_path)
        rs = find_binary("rs41mod", self.decoder_path)
        argv_fsk, argv_rs = build_decoder_commands(self.channel.station_hz, fsk, rs)
        opts = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
                "stderr": subprocess.DEVNULL, "bufsize": 0}
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            self.demod = subprocess.Popen(argv_fsk, creationflags=creationflags, **opts)
            self.decoder = subprocess.Popen(argv_rs, stdin=self.demod.stdout, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, creationflags=creationflags, bufsize=0)
            if self.demod.stdout:
                self.demod.stdout.close()  # escritor externo não prende a saída na aplicação
        except Exception:
            self.stop()
            raise
        self._stop.clear()
        self._writer = threading.Thread(target=self._write_loop, daemon=True, name="sonde-iq-writer")
        self._reader = threading.Thread(target=self._read_loop, daemon=True, name="sonde-json-reader")
        self._writer.start()
        self._reader.start()
        self.on_status("RS41: recebendo IQ do SDR atual (48 kS/s para fsk_demod/rs41mod)")

    def feed(self, iq, center_hz: float, sample_rate: int):
        """Chamado na thread DSP: somente copia bloco para fila limitada."""
        if self._stop.is_set() or int(sample_rate) != self.channel.sample_rate:
            return
        try:
            self._queue.put_nowait((np.asarray(iq, dtype=np.complex64).copy(), float(center_hz)))
        except queue.Full:
            self.dropped += 1

    def _write_loop(self):
        try:
            while not self._stop.is_set():
                try:
                    item = self._queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if item is None:
                    break
                data = self.channel.convert(*item)
                if data and self.demod and self.demod.stdin:
                    self.demod.stdin.write(data)
                if self.demod and self.demod.poll() is not None:
                    raise RuntimeError(f"fsk_demod encerrou com código {self.demod.returncode}")
                if self.decoder and self.decoder.poll() is not None:
                    raise RuntimeError(f"rs41mod encerrou com código {self.decoder.returncode}")
        except (OSError, ValueError, BrokenPipeError, RuntimeError) as exc:
            if not self._stop.is_set():
                self._startup_error = str(exc)
                self.on_status(f"RS41: erro no pipeline: {exc}")
        finally:
            if self.demod and self.demod.stdin:
                try:
                    self.demod.stdin.close()
                except OSError:
                    pass

    def _read_loop(self):
        if not self.decoder or not self.decoder.stdout:
            return
        try:
            for raw in self.decoder.stdout:
                if self._stop.is_set():
                    break
                if not raw.lstrip().startswith(b"{"):
                    continue
                try:
                    data = json.loads(raw)
                    recs = parse_radiosondes(data)
                except (ValueError, UnicodeError, TypeError):
                    continue
                for record in recs:
                    self.received += 1
                    self.on_decoded(record, data)
        except OSError as exc:
            if not self._stop.is_set():
                self.on_status(f"RS41: saída do decoder interrompida: {exc}")

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        for proc in (self.demod, self.decoder):
            if proc and proc.poll() is None:
                proc.terminate()
        for proc in (self.demod, self.decoder):
            if proc:
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        for t in (self._writer, self._reader):
            if t and t.is_alive() and t is not threading.current_thread():
                t.join(timeout=1)
        self._writer = self._reader = None
        self.demod = self.decoder = None
