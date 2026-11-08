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

import numpy as np
from scipy.signal import resample_poly

from .transcribe import find_callsigns

log = logging.getLogger(__name__)


class LiveCaptionWorker:
    """Acumula blocos de áudio e reconhece trechos em thread separada."""

    def __init__(self, on_result, on_error=None, sample_rate=48000, seconds=4.0,
                 model_size="tiny", language=None, model=None):
        self.on_result = on_result
        self.on_error = on_error
        self.rate = int(sample_rate)
        self.target_samples = int(self.rate * max(2.0, float(seconds)))
        self.model_size = model_size
        self.language = language if language not in ("", "auto") else None
        self._model = model
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
            self._queue.put_nowait((packet, time.time()))
        except queue.Full:
            # Preferimos a transmissão mais recente: nunca bloquear o receptor.
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((packet, time.time()))
            except queue.Empty:
                pass

    def _get_model(self):
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel
        self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def _run(self):
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if task is None:
                return
            audio, timestamp = task
            try:
                model = self._get_model()
                # faster-whisper consome PCM float32 mono a 16 kHz.
                audio16 = resample_poly(audio, 16000, self.rate).astype(np.float32)
                segments, info = model.transcribe(audio16, language=self.language,
                                                   vad_filter=True, beam_size=1)
                text = " ".join(x.text.strip() for x in segments).strip()
                if text and not self._stop.is_set():
                    lang = getattr(info, "language", "") or (self.language or "")
                    self.on_result(timestamp, text, find_callsigns(text), lang)
            except Exception as exc:  # noqa: BLE001
                log.warning("Legendas ao vivo: %s", exc)
                if self.on_error is not None and not self._stop.is_set():
                    self.on_error(str(exc))

    def stop(self):
        self._stop.set()
        self._chunks.clear()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
