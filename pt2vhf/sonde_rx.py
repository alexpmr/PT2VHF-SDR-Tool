"""Receptor RS41 por amostras IQ do *mesmo* SDR usado no waterfall.

DSP próprio: deslocamento complexo para FI +12 kHz e decimação a 48 kS/s.
Decodificação FSK/FEC/telemetria por fsk_demod e rs41mod (projeto auto_rx,
programas externos de código aberto). O Setup/Portable Windows embarca cópias
compiladas em ``sonde_decoders/`` (ver packaging/build_sonde_decoders.sh);
caminho configurado pelo usuário tem prioridade, depois a cópia embarcada e
por fim o PATH.
Executa subprocessos sem shell, fora da thread de recepção; desativado por padrão.
"""
from __future__ import annotations

import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import json
import collections
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly, butter, sosfilt
from .traffic import parse_radiosondes

OUTPUT_RATE = 48000
SIGNAL_OFFSET_HZ = 0  # centralizar portadora em 0 Hz; máscara FSK: -5 a +5 kHz


BUNDLED_DIRNAME = "sonde_decoders"


def bundled_decoder_dir(dirname: str = BUNDLED_DIRNAME) -> Path | None:
    """Pasta dos decodificadores embarcados (PyInstaller) ou compilados localmente."""
    candidates = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(Path(base) / dirname)
    candidates.append(Path(__file__).resolve().parent.parent / "packaging" / dirname)
    for folder in candidates:
        if folder.is_dir():
            return folder
    return None


def bundled_binary(executable: str, dirname: str = BUNDLED_DIRNAME) -> str | None:
    folder = bundled_decoder_dir(dirname)
    if folder is None:
        return None
    for name in (executable + ".exe", executable) if os.name == "nt" else (executable,):
        path = folder / name
        if path.is_file() and (os.name == "nt" or os.access(path, os.X_OK)):
            return str(path)
    return None


def locate_binary(executable: str, supplied_path: str = "",
                  dirname: str = BUNDLED_DIRNAME) -> tuple[str | None, str]:
    """Resolve sem executar: (caminho, origem) com origem 'usuário', 'embarcado' ou 'PATH'.

    Um caminho explícito do usuário prevalece e não cai para outra cópia se
    estiver errado (evita usar silenciosamente um programa diferente).
    """
    name = str(supplied_path or "").strip().strip('"').strip("'")
    if name and name.lower() not in (executable.lower(), executable.lower() + ".exe"):
        located = shutil.which(name)
        if not located and Path(name).expanduser().is_file():
            located = str(Path(name).expanduser())
        return (str(Path(located).resolve()) if located else None), "usuário"
    bundled = bundled_binary(executable, dirname)
    if bundled:
        return str(Path(bundled).resolve()), "embarcado"
    located = shutil.which(executable)
    return (str(Path(located).resolve()) if located else None), "PATH"


def find_binary(executable: str, supplied_path: str = "") -> str:
    """Sem download automático ou execução de scripts: usuário > embarcado > PATH."""
    if not executable:
        raise ValueError("Nome vazio do decodificador")
    located, origin = locate_binary(executable, supplied_path)
    if not located:
        where = ("o caminho configurado não existe" if origin == "usuário"
                 else "nenhuma cópia embarcada nem no PATH")
        raise FileNotFoundError(
            f"{executable} indisponível ({where}). Reinstale o PT2VHF SDR Tool, "
            f"limpe o campo para usar a cópia embarcada ou indique o executável.")
    return located


def build_decoder_commands(freq_hz: float, fsk_binary: str, rs41_binary: str):
    if not math.isfinite(freq_hz) or not 400e6 <= freq_hz <= 406e6:
        raise ValueError("A recepção RS41 configurada suporta a faixa 400–406 MHz")
    demod = [fsk_binary, "--cs16", "-b", "-5000", "-u", "5000",
             "-s", "--mask", "5000", "--nsym=300", "-p", "5", "--stats=5",
             "2", "48000", "4800", "-", "-"]
    decoder = [rs41_binary, "--ptu2", "--json", "--jsnsubfrm1",
               "--softin", "-i", "--jsn_cfq", str(int(round(freq_hz)))]
    return demod, decoder


class ChannelIQ:
    """Canal complexo centrado na portadora (0 Hz), saída IQ int16 48 kHz.

    Uma fase contínua é mantida entre blocos. Cada bloco é reamostrado com
    resample_poly; blocos grandes de SDR fornecem margem de filtro na entrada.
    """
    def __init__(self, sample_rate: int, station_hz: float, output_rate: int = OUTPUT_RATE,
                 cutoff_hz: float = 19_000):
        self.sample_rate = int(sample_rate)
        self.station_hz = float(station_hz)
        self.output_rate = int(output_rate)
        self.samples = 0
        self._center = None
        self._tail = np.empty(0, dtype=np.complex64)
        if self.sample_rate < 2 * self.output_rate:
            raise ValueError(f"IQ com taxa inferior a {2 * self.output_rate // 1000} kS/s")
        self._gcd = math.gcd(self.sample_rate, self.output_rate)
        self._up, self._down = self.output_rate // self._gcd, self.sample_rate // self._gcd
        # Taxas múltiplas da saída: filtro IIR contínuo + seleção com fase
        # persistente entre blocos, sem saltos de símbolos a cada read() do SDR.
        self._sos = (butter(10, cutoff_hz, btype="lowpass", fs=self.sample_rate,
                            output="sos") if self._up == 1 else None)
        self._zi = (np.zeros((len(self._sos), 2), dtype=np.complex128)
                    if self._sos is not None else None)

    def convert(self, block, center_hz: float) -> bytes:
        narrow = self.channelize(block, center_hz)
        if narrow.size == 0:
            return b""
        # O fsk_demod moderno espera I/Q signed 16 bit little-endian, intercalado,
        # portadora no centro do canal (-5 a +5 kHz), não na antiga FI +12 kHz.
        vals = np.stack((narrow.real, narrow.imag), axis=-1)
        ints = np.round(np.clip(vals, -1, 1) * 30000).astype("<i2")
        return ints.tobytes()

    def channelize(self, block, center_hz: float) -> np.ndarray:
        """Canal complexo centrado na estação, na taxa de saída (complex64)."""
        samples = np.asarray(block, dtype=np.complex64).reshape(-1)
        if samples.size == 0:
            return np.empty(0, dtype=np.complex64)
        center_hz = float(center_hz)
        off = self.station_hz - SIGNAL_OFFSET_HZ - center_hz
        if abs(off) >= self.sample_rate / 2 - max(30000, self.output_rate / 2):
            raise ValueError("Frequência da estação fora da banda IQ capturada")
        if self._center != center_hz:
            self._center = center_hz
            self.samples = 0
            self._tail = np.empty(0, dtype=np.complex64)
            if self._zi is not None:
                self._zi.fill(0)
        position = np.arange(samples.size, dtype=np.float64) + self.samples
        self.samples += samples.size
        translated = (samples * np.exp(-2j * math.pi * off / self.sample_rate * position)).astype(np.complex64)
        if self._sos is not None:
            # Estado do filtro e relógio de amostragem contínuos, mesmo com
            # blocos de tamanho variável ou não múltiplo do fator de redução.
            filtered, self._zi = sosfilt(self._sos, translated, zi=self._zi)
            first = (-(self.samples - len(samples))) % self._down
            narrow = filtered[first::self._down]
        else:
            # Fallback racional para taxas arbitrárias com histórico de entrada.
            prefix = self._tail
            n_prefix_out = math.ceil(len(prefix) * self._up / self._down)
            joined = np.concatenate((prefix, translated))
            narrow = resample_poly(joined, self._up, self._down)[n_prefix_out:]
            self._tail = joined[-min(len(joined), 10 * self._down):].copy()
        return np.asarray(narrow, dtype=np.complex64)


class RS41Receiver:
    """Encaminha amostras já capturadas ao fsk_demod e rs41mod, sem outro dongle."""

    def __init__(self, sample_rate: int, station_hz: float, on_decoded, on_status=None,
                 fsk_path="", decoder_path="", on_frame=None):
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
        self.on_frame = on_frame
        self.iq_blocks = 0
        self.iq_samples = 0
        self.iq_bytes = 0
        self.json_frames = 0
        self.unpositioned_frames = 0
        self.invalid_json = 0
        self.last_frame = ""
        self.last_demod_stats = ""
        self.last_error = ""
        self._stderr_threads = []
        self._capture_lock = threading.Lock()
        self._capture_file = None
        self._capture_left = 0
        self._capture_name = ""
        self._capture_done = ""

    def start(self):
        fsk = find_binary("fsk_demod", self.fsk_path)
        rs = find_binary("rs41mod", self.decoder_path)
        argv_fsk, argv_rs = build_decoder_commands(self.channel.station_hz, fsk, rs)
        opts = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE, "bufsize": 0}
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            self.demod = subprocess.Popen(argv_fsk, creationflags=creationflags, **opts)
            self.decoder = subprocess.Popen(argv_rs, stdin=self.demod.stdout, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, creationflags=creationflags, bufsize=0)
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
        for proc, label in ((self.demod, "FSK"), (self.decoder, "RS41")):
            if proc and proc.stderr:
                thr = threading.Thread(target=self._stderr_loop, args=(proc.stderr, label),
                                       daemon=True, name="sonde-" + label.lower() + "-stderr")
                thr.start()
                self._stderr_threads.append(thr)
        self.on_status("RS41: demoduladores iniciados; aguardando quadros válidos (IQ 48 kS/s)")

    def feed(self, iq, center_hz: float, sample_rate: int):
        """Chamado na thread DSP: somente copia bloco para fila limitada."""
        if self._stop.is_set():
            return
        if int(sample_rate) != self.channel.sample_rate:
            self.dropped += 1
            self.last_error = "Taxa de IQ mudou; reinicie o decodificador RS41"
            return
        try:
            incoming = np.asarray(iq, dtype=np.complex64).copy()
            self._queue.put_nowait((incoming, float(center_hz)))
            self.iq_blocks += 1
            self.iq_samples += len(incoming)
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
                if data:
                    self.iq_bytes += len(data)
                    self._capture_data(data)
                    if self.demod and self.demod.stdin:
                        self.demod.stdin.write(data)
                if self.demod and self.demod.poll() is not None:
                    raise RuntimeError(f"fsk_demod encerrou com código {self.demod.returncode}")
                if self.decoder and self.decoder.poll() is not None:
                    raise RuntimeError(f"rs41mod encerrou com código {self.decoder.returncode}")
        except (OSError, ValueError, BrokenPipeError, RuntimeError) as exc:
            if not self._stop.is_set():
                self._startup_error = str(exc)
                self.last_error = str(exc)
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
                except (ValueError, UnicodeError, TypeError):
                    self.invalid_json += 1
                    continue
                self.json_frames += 1
                self.last_frame = str(data.get("frame", "—")) if isinstance(data, dict) else "—"
                try:
                    recs = parse_radiosondes(data)
                except (ValueError, UnicodeError, TypeError):
                    recs = []
                if not recs:
                    self.unpositioned_frames += 1
                    if self.on_frame:
                        self.on_frame(data)
                for record in recs:
                    self.received += 1
                    self.on_decoded(record, data)
        except OSError as exc:
            if not self._stop.is_set():
                self.last_error = str(exc)
                self.on_status(f"RS41: saída do decoder interrompida: {exc}")

    def _stderr_loop(self, pipe, label):
        try:
            for line in pipe:
                if self._stop.is_set():
                    break
                msg = line.decode("utf-8", errors="replace").strip()[-300:]
                if not msg:
                    continue
                if label == "FSK" and ("SNR" in msg.upper() or "fsk" in msg.lower()
                                       or "stats" in msg.lower()):
                    self.last_demod_stats = msg
                if "error" in msg.lower() or "usage" in msg.lower() or "invalid" in msg.lower():
                    self.last_error = f"{label}: {msg}"
                    self.on_status(f"RS41: {self.last_error}")
        except OSError:
            return

    def diagnostics(self):
        """Métricas para exibição na GUI; não confundir IQ recebido com quadro válido."""
        return {
            "iq_blocks": self.iq_blocks, "iq_samples": self.iq_samples,
            "iq_bytes": self.iq_bytes, "dropped": self.dropped,
            "json_frames": self.json_frames, "positions": self.received,
            "unpositioned_frames": self.unpositioned_frames,
            "invalid_json": self.invalid_json,
            "frame": self.last_frame, "demod": self.last_demod_stats,
            "error": self.last_error or self._startup_error or "",
            "capture": self._capture_done,
            "fsk_alive": self.demod is not None and self.demod.poll() is None,
            "decoder_alive": self.decoder is not None and self.decoder.poll() is None,
            "frequency": self.channel.station_hz,
            "sample_rate": self.channel.sample_rate,
        }

    def start_capture(self, path, duration=20):
        """Salva somente 20 s de IQ reduzido 48 kS/s para diagnóstico reproduzível."""
        file = Path(path).expanduser()
        file.parent.mkdir(parents=True, exist_ok=True)
        with self._capture_lock:
            if self._capture_file is not None:
                raise RuntimeError("Já existe uma captura IQ em andamento")
            self._capture_file = file.open("wb")
            self._capture_left = min(60, max(1, int(duration))) * OUTPUT_RATE * 4
            self._capture_name = str(file)
            self._capture_done = ""

    def _capture_data(self, data):
        with self._capture_lock:
            if self._capture_file is not None:
                chunk = data[:self._capture_left]
                self._capture_file.write(chunk)
                self._capture_left -= len(chunk)
                if self._capture_left <= 0:
                    self._close_capture()

    def _close_capture(self):
        """Deve ser chamada com o lock adquirido."""
        if self._capture_file is not None:
            self._capture_file.close()
            self._capture_file = None
            self._capture_done = self._capture_name

    def stop(self):
        self._stop.set()
        with self._capture_lock:
            self._close_capture()
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
        for t in self._stderr_threads:
            if t.is_alive() and t is not threading.current_thread():
                t.join(timeout=0.5)
        self._stderr_threads.clear()
        self._writer = self._reader = None
        self.demod = self.decoder = None


def synthetic_pipeline_check(fsk_binary: str | None = None, rs41_binary: str | None = None,
                             frames: int = 4, timeout: float = 90.0) -> list[dict]:
    """Executa IQ RS41 *sintético* -> ChannelIQ -> fsk_demod -> rs41mod e retorna os JSON.

    Usado no autoteste do executável para provar pipes binários, argumentos e
    binários embarcados. Não é homologação RF: não substitui IQ real de sonda.
    """
    from .sonde_synth import rs41_frame, rs41_iq
    fsk = fsk_binary or find_binary("fsk_demod")
    rs = rs41_binary or find_binary("rs41mod")
    station, rate = 403_000_000.0, 240_000
    center = station - 30_000
    iq = rs41_iq([rs41_frame(frame_nb=1000 + i) for i in range(frames)], rate,
                 offset_hz=station - center)
    channel = ChannelIQ(rate, station)
    data = b"".join(channel.convert(iq[i:i + 16384], center) for i in range(0, len(iq), 16384))
    argv_fsk, argv_rs = build_decoder_commands(station, fsk, rs)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    demod = subprocess.Popen(argv_fsk, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, creationflags=flags)
    decoder = subprocess.Popen(argv_rs, stdin=demod.stdout, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, creationflags=flags)
    demod.stdout.close()
    feeder = threading.Thread(target=lambda: (demod.stdin.write(data), demod.stdin.close()),
                              daemon=True)
    feeder.start()
    try:
        out, _ = decoder.communicate(timeout=timeout)
    finally:
        for proc in (demod, decoder):
            if proc.poll() is None:
                proc.kill()
        demod.wait(timeout=5)
    result = []
    for line in out.splitlines():
        if line.lstrip().startswith(b"{"):
            try:
                result.append(json.loads(line))
            except ValueError:
                pass
    return result
