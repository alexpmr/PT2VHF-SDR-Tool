"""Saída de áudio (sounddevice/PortAudio) e gravadores WAV."""
from __future__ import annotations

import logging
import threading
import time
import wave
from collections import deque
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

    def write(self, x: np.ndarray):
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
