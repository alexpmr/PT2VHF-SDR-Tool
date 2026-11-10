"""Saída de áudio (sounddevice/PortAudio) e gravadores WAV."""
from __future__ import annotations

import logging
import threading
import time
import wave
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


def list_output_devices() -> list[tuple[int, str]]:
    try:
        import sounddevice as sd
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                api = sd.query_hostapis(d["hostapi"])["name"]
                out.append((i, f"{d['name']} ({api})"))
        return out
    except Exception:  # noqa: BLE001
        return []


class AudioOutput:
    """Buffer circular alimentado pela thread DSP e consumido pelo callback da placa de som.

    Compensa diferenças de clock entre SDR e placa de som descartando/preenchendo.
    """

    def __init__(self, rate: int = 48_000, device=None, latency_s: float = 0.15):
        self.rate = rate
        self.device = device
        self.target = int(rate * latency_s)
        self.max_fill = int(rate * 0.5)
        self._buf: deque[np.ndarray] = deque()
        self._fill = 0
        self._lock = threading.Lock()
        self._stream = None
        self.available = False
        self.error = ""
        self.underruns = 0
        self._primed = False

    def start(self):
        try:
            import sounddevice as sd
            self._stream = sd.OutputStream(samplerate=self.rate, channels=1, dtype="float32",
                                           device=self.device, callback=self._cb,
                                           blocksize=1024, latency="low")
            self._stream.start()
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            log.warning("Sem saída de áudio: %s", e)
            self.available = False

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None

    def write(self, samples: np.ndarray):
        if not self.available or len(samples) == 0:
            return
        with self._lock:
            self._buf.append(samples.astype(np.float32))
            self._fill += len(samples)
            while self._fill > self.max_fill and self._buf:
                self._fill -= len(self._buf.popleft())

    def _cb(self, outdata, frames, _time, _status):
        out = outdata[:, 0]
        with self._lock:
            if not self._primed and self._fill < self.target:
                out[:] = 0
                return
            self._primed = True
            i = 0
            while i < frames and self._buf:
                chunk = self._buf[0]
                n = min(frames - i, len(chunk))
                out[i:i + n] = chunk[:n]
                if n == len(chunk):
                    self._buf.popleft()
                else:
                    self._buf[0] = chunk[n:]
                self._fill -= n
                i += n
            if i < frames:
                out[i:] = 0
                self.underruns += 1
                self._primed = False


# WAV RIFF is limited to 32-bit chunk sizes. Reserve 64 KiB for headers/chunks.
MAX_RIFF_DATA_BYTES = 0xFFFFFFFF - 65536


class WavSizeLimitError(OSError):
    """The next write would exceed the safe RIFF/WAV file size."""


class WavRecorder:
    """Grava WAV PCM 16 bits (mono = áudio, estéreo = IQ)."""

    def __init__(self, path: Path, rate: int, channels: int):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.channels = channels
        self.w = wave.open(str(path), "wb")
        self.w.setnchannels(channels)
        self.w.setsampwidth(2)
        self.w.setframerate(rate)
        self.started = time.time()
        self.samples = 0
        self.max_data_bytes = MAX_RIFF_DATA_BYTES

    def write(self, x: np.ndarray):
        # Preflight before allocating or calling wave.writeframes(), which would
        # otherwise fail/overflow once the RIFF 32-bit size field is exhausted.
        new_bytes = len(x) * self.channels * 2
        existing_bytes = self.samples * self.channels * 2
        if new_bytes > self.max_data_bytes - existing_bytes:
            raise WavSizeLimitError(
                "WAV RIFF perto do limite de 4 GiB; gravação encerrada sem corromper arquivo")
        if self.channels == 2:
            inter = np.empty(len(x) * 2, np.float32)
            inter[0::2] = x.real
            inter[1::2] = x.imag
            data = inter
        else:
            data = x
        self.w.writeframes((np.clip(data, -1, 1) * 32767).astype("<i2").tobytes())
        self.samples += len(x)

    def close(self):
        self.w.close()


class ActivityRecorder:
    """Gravação tipo VOX: grava só enquanto há transmissão (squelch aberto).

    - pré-gravação (`preroll_s`) para não cortar o começo da fala e "cauda" após o squelch fechar;
    - `single_file=False`: um WAV por transmissão em <pasta>/<AAAA-MM-DD>/HHMMSS_<freq>MHz_<modo>.wav,
      descartando as curtas demais e dividindo as muito longas;
    - `single_file=True`: um único WAV por sessão, só com as transmissões (sem os silêncios).
    Cada transmissão concluída gera um evento (dict) com arquivo, frequência, modo, início e duração.
    """

    def __init__(self, folder: str, rate: int = 48_000, tail_s: float = 1.5,
                 min_s: float = 1.0, max_s: float = 300.0, preroll_s: float = 0.5,
                 single_file: bool = False):
        self.folder = Path(folder)
        self.rate = rate
        self.tail_s, self.min_s, self.max_s = tail_s, min_s, max_s
        self.preroll = int(rate * preroll_s)
        self.single_file = single_file
        self._pre: deque[np.ndarray] = deque()
        self._pre_n = 0
        self._rec: WavRecorder | None = None
        self._session: WavRecorder | None = None
        self._closed_for = 0.0
        self._tx_samples = 0
        self._info: dict = {}

    @property
    def active(self) -> bool:
        return self._info != {}

    @property
    def session_path(self) -> Path | None:
        return self._session.path if self._session else None

    def _new_file(self, freq, mode, tag=""):
        now = datetime.now()
        name = f"{now:%H%M%S}_{freq / 1e6:.4f}MHz_{mode}{tag}.wav"
        path = self.folder / f"{now:%Y-%m-%d}" / name
        k = 2
        while path.exists():  # duas transmissões no mesmo segundo
            path = path.with_name(f"{name[:-4]}_{k}.wav")
            k += 1
        return WavRecorder(path, self.rate, 1)

    def _keep_preroll(self, audio):
        if self.preroll <= 0 or not len(audio):
            return
        self._pre.append(audio.astype(np.float32).copy())
        self._pre_n += len(audio)
        while self._pre and self._pre_n - len(self._pre[0]) >= self.preroll:
            self._pre_n -= len(self._pre.popleft())

    def process(self, audio: np.ndarray, opened: bool, freq: float, mode: str, level_db: float):
        dt = len(audio) / self.rate
        if not self._info:
            if not opened:
                self._keep_preroll(audio)
                return None
            if self.single_file:
                if self._session is None:
                    self._session = self._new_file(freq, mode, "_VOX")
                self._rec = self._session
            else:
                self._rec = self._new_file(freq, mode)
            self._info = {"file": str(self._rec.path), "freq": freq, "mode": mode, "start": time.time(),
                          "peak_db": level_db}
            self._closed_for = 0.0
            self._tx_samples = 0
            self._pre_written = self._pre_n
            for chunk in self._pre:
                self._rec.write(chunk)
            self._pre.clear()
            self._pre_n = 0
        if len(audio):
            self._rec.write(audio)
            self._tx_samples += len(audio)
        if opened:
            self._info["peak_db"] = max(self._info["peak_db"], level_db)
        self._closed_for = 0.0 if opened else self._closed_for + dt
        dur = self._tx_samples / self.rate
        if self._closed_for >= self.tail_s or dur >= self.max_s or abs(freq - self._info["freq"]) > 1:
            return self._finish()
        return None

    def _finish(self):
        rec, info = self._rec, dict(self._info)
        self._info = {}
        info["duration"] = max(0.0, self._tx_samples / self.rate - self._closed_for)  # sem a pré-gravação
        if self.single_file:
            return info if info["duration"] >= self.min_s else None
        rec.close()
        if info["duration"] < self.min_s:
            try:
                rec.path.unlink()
            except OSError:
                pass
            return None
        return info

    def close(self):
        ev = self._finish() if self._info else None
        if self._session is not None:
            self._session.close()
            self._session = None
        return ev
