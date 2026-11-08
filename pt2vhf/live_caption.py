"""Legendas locais quase em tempo real para a fonia demodulada.

Usa faster-whisper opcional, fora da thread de recepção. Nunca transmite
áudio pela rede. O usuário deve ter o backend e o modelo disponíveis;
a aplicação não anuncia transcrição funcional quando não estão instalados.
"""
from __future__ import annotations

import logging
import math
import queue
import threading
import time
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from .transcribe import find_callsigns
from .config import config_dir

log = logging.getLogger(__name__)

ALLOWED_MODELS = frozenset(("tiny", "base", "small"))


def local_model_path(size: str) -> Path:
    if size not in ALLOWED_MODELS:
        raise ValueError("Modelo Whisper desconhecido")
    return config_dir() / "models" / ("whisper-" + size)


def model_installed(size: str) -> bool:
    path = local_model_path(size)
    return (path / "model.bin").is_file() and (path / "config.json").is_file()


def install_local_model(size: str) -> Path:
    """Baixa SOMENTE por ação explícita; a inferência posterior não usa a Internet."""
    from faster_whisper.utils import download_model
    path = local_model_path(size)
    path.mkdir(parents=True, exist_ok=True)
    download_model(size, output_dir=str(path))
    if not model_installed(size):
        raise RuntimeError("O download não produziu um modelo completo.")
    return path



class LiveCaptionWorker:
    """Acumula blocos de áudio e reconhece trechos em thread separada."""

    def __init__(self, on_result, on_error=None, sample_rate=48000, seconds=4.0,
                 model_size="tiny", language=None, model=None, meta_provider=None):
        self.on_result = on_result
        self.on_error = on_error
        self.rate = int(sample_rate)
        self.target_samples = int(self.rate * max(2.0, float(seconds)))
        self.model_size = model_size
        self.language = language if language not in ("", "auto") else None
        self._model = model
        self.meta_provider = meta_provider
        self._chunks = []
        self._pending_samples = 0
        self._queue: queue.Queue = queue.Queue(maxsize=2)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="legendas-sdr")
        self._thread.start()

    def feed(self, audio):
        """Chamado pelo DSP; armazenamento O(n), sem inferência/IO na thread de RF."""
        if self._stop.is_set():
            return
        buf = np.asarray(audio, dtype=np.float32)
        if buf.size == 0:
            return
        self._chunks.append(buf.copy())
        self._pending_samples += len(buf)
        if self._pending_samples < self.target_samples:
            return
        packet = np.concatenate(self._chunks)
        self._chunks.clear()
        self._pending_samples = 0
        if float(np.max(np.abs(packet))) < 0.009:
            return
        try:
            self._queue.put_nowait((packet, time.time(), self.meta_provider() if self.meta_provider else None))
        except queue.Full:
            # Preferimos a transmissão mais recente: nunca bloquear o receptor.
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((packet, time.time(), self.meta_provider() if self.meta_provider else None))
            except queue.Empty:
                pass

    def _get_model(self):
        if self._model is not None:
            return self._model
        if not model_installed(self.model_size):
            raise FileNotFoundError(
                f"Modelo {self.model_size} não instalado. Use 'Baixar modelo' na aba Legendas.")
        from faster_whisper import WhisperModel
        self._model = WhisperModel(str(local_model_path(self.model_size)),
                                   device="cpu", compute_type="int8",
                                   cpu_threads=4, local_files_only=True)
        return self._model

    def _run(self):
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if task is None:
                return
            audio, timestamp, meta = task
            try:
                model = self._get_model()
                # faster-whisper consome PCM float32 mono a 16 kHz.
                audio16 = resample_poly(audio, 16000, self.rate).astype(np.float32)
                segments, info = model.transcribe(audio16, language=self.language,
                                                   vad_filter=True, beam_size=1)
                text = " ".join(x.text.strip() for x in segments).strip()
                if text and not self._stop.is_set():
                    lang = getattr(info, "language", "") or (self.language or "")
                    self.on_result(timestamp, text, find_callsigns(text), lang, meta)
            except Exception as exc:  # noqa: BLE001
                log.warning("Legendas ao vivo: %s", exc)
                if self.on_error is not None and not self._stop.is_set():
                    self.on_error(str(exc))
                if isinstance(exc, (FileNotFoundError, ImportError)):
                    return

    def stop(self):
        self._stop.set()
        self._chunks.clear()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
