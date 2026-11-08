"""Bounded asynchronous inference for IQ classifier; never blocks the DSP thread."""
from __future__ import annotations
import queue
import threading
import time
import numpy as np
from .iq_classifier import IQClassifier

class IQClassificationWorker:
    def __init__(self, model_path, on_result, on_error=None, min_confidence=0.8):
        self.on_result, self.on_error = on_result, on_error
        self.model_path, self.min_confidence = model_path, min_confidence
        self.dropped = 0
        self._queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="iq-classifier", daemon=True)
        self._thread.start()

    def feed(self, iq, frequency_hz=None):
        if self._stop.is_set():
            return False
        chunk = np.asarray(iq, np.complex64)
        if chunk.size < 2048:
            return False
        item = (chunk.copy(), frequency_hz, time.time())
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self.dropped += 1
                self._queue.put_nowait(item)
            except queue.Empty:
                return False
        return True

    def _run(self):
        try:
            classifier = IQClassifier(self.model_path, self.min_confidence)
        except Exception as exc:
            if self.on_error:
                self.on_error(str(exc))
            return
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                break
            iq, frequency, timestamp = item
            try:
                result = classifier.predict(iq)
                if not self._stop.is_set():
                    self.on_result(result, frequency, timestamp)
            except Exception as exc:
                if self.on_error and not self._stop.is_set():
                    self.on_error(str(exc))

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
