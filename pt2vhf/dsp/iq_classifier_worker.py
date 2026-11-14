"""Bounded asynchronous inference for IQ classifier; never blocks the DSP thread."""
from __future__ import annotations
import queue
import threading
import time
import numpy as np
from .iq_classifier import IQClassifier

# A DSP callback must not copy or enqueue arbitrarily long IQ buffers.
# 250 ms is a conservative *input budget*, not a measured latency guarantee.
# The worker's 48 kS/s target yields at most 12,000 output samples; an
# independent absolute input cap protects against pathological sample rates.
MAX_WORKER_INPUT_SAMPLES = 768_000
MAX_WORKER_OUTPUT_SAMPLES = 12_000

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
        # Preflight ordinary DSP ndarray/list inputs *before* conversion:
        # np.asarray() and copy() may otherwise allocate unbounded memory on
        # the real-time receive thread, even with a one-slot output queue.
        if isinstance(iq, np.ndarray):
            count = iq.size
        elif isinstance(iq, (list, tuple)):
            count = len(iq)
        else:
            count = None
        if count is not None and count > MAX_WORKER_INPUT_SAMPLES:
            return False
        if count is not None and (
            count * ratio.numerator + ratio.denominator - 1
        ) // ratio.denominator > MAX_WORKER_OUTPUT_SAMPLES:
            return False
        # A malformed buffer must not raise into the SDR receive callback.
        try:
            chunk = np.asarray(iq, np.complex64).reshape(-1)
        except (TypeError, ValueError, OverflowError):
            return False
        output_count = (
            chunk.size * ratio.numerator + ratio.denominator - 1
        ) // ratio.denominator
        if (chunk.size > MAX_WORKER_INPUT_SAMPLES
                or not 2048 <= output_count <= MAX_WORKER_OUTPUT_SAMPLES):
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
