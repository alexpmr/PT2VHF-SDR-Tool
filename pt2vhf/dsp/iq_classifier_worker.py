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

    def feed(self, iq, frequency_hz=None, sample_rate=48000):
        if self._stop.is_set():
            return False
        # Feed is called by the SDR/DSP path. Never run polyphase FIR
        # resampling here: it can stall reception at high input rates.
        try:
            rate = float(sample_rate)
        except (TypeError, ValueError, OverflowError):
            return False
        if not np.isfinite(rate) or rate <= 0 or not rate.is_integer():
            return False
        from fractions import Fraction
        ratio = Fraction(48000, int(rate))
        # Bound pathological ratios before enqueueing expensive FIR work.
        if max(ratio.numerator, ratio.denominator) > 4096:
            return False
        # A malformed buffer must not raise into the SDR receive callback.
        try:
            chunk = np.asarray(iq, np.complex64).reshape(-1)
        except (TypeError, ValueError, OverflowError):
            return False
        if (chunk.size * ratio.numerator + ratio.denominator - 1) // ratio.denominator < 2048:
            return False
        item = (chunk.copy(), frequency_hz, time.time(),
                ratio.numerator, ratio.denominator)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self.dropped += 1
                try:
                    self._queue.put_nowait(item)
                except queue.Full:
                    # Another producer may have filled the slot after get_nowait.
                    return False
            except queue.Empty:
                return False
        return True

    def _run(self):
        try:
            classifier = IQClassifier(self.model_path, self.min_confidence)
        except Exception as exc:
            # Do not keep accepting IQ when the inference thread cannot start.
            self._stop.set()
            if self.on_error:
                try:
                    self.on_error(str(exc))
                except Exception:
                    # A faulty UI/error callback must not escape this daemon thread.
                    pass
            return
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                break
            iq, frequency, timestamp, up, down = item
            try:
                if (up, down) != (1, 1):
                    from scipy.signal import resample_poly
                    iq = resample_poly(iq, up, down).astype(np.complex64)
                result = classifier.predict(iq)
                if not self._stop.is_set():
                    self.on_result(result, frequency, timestamp)
            except Exception as exc:
                if self.on_error and not self._stop.is_set():
                    try:
                        self.on_error(str(exc))
                    except Exception:
                        # If the error handler itself is broken, fail closed:
                        # never enqueue more IQ into a dead inference worker.
                        self._stop.set()
                        return

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
