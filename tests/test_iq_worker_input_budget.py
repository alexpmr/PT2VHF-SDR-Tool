"""Synthetic input-budget guards for the experimental IQ worker.

These checks prevent oversized DSP-thread copies. They do not benchmark CPU,
prove RF accuracy, or authorize neural integration into the stable receiver.
"""
import threading

import numpy as np

from pt2vhf.dsp import iq_classifier_worker as module


def _waiting_worker(monkeypatch, tmp_path):
    started, release = threading.Event(), threading.Event()

    class WaitingClassifier:
        def __init__(self, *args, **kwargs):
            started.set()
            release.wait(timeout=5)

        def predict(self, samples):
            return "unused"

    monkeypatch.setattr(module, "IQClassifier", WaitingClassifier)
    worker = module.IQClassificationWorker(tmp_path / "unused.onnx", lambda *_: None)
    assert started.wait(timeout=2)
    return worker, release


def test_worker_rejects_oversized_ndarray_before_numpy_conversion(monkeypatch, tmp_path):
    worker, release = _waiting_worker(monkeypatch, tmp_path)
    try:
        oversized = np.broadcast_to(np.complex64(1), (module.MAX_WORKER_INPUT_SAMPLES + 1,))
        def forbidden(*args, **kwargs):
            raise AssertionError("oversized ndarray must not be converted")
        with monkeypatch.context() as patch:
            patch.setattr(module.np, "asarray", forbidden)
            assert worker.feed(oversized, sample_rate=3_072_000) is False
        assert worker._queue.empty()
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)


def test_worker_rejects_oversized_flat_list_before_conversion(monkeypatch, tmp_path):
    worker, release = _waiting_worker(monkeypatch, tmp_path)
    try:
        oversized = [1j] * (module.MAX_WORKER_OUTPUT_SAMPLES + 1)
        def forbidden(*args, **kwargs):
            raise AssertionError("oversized list must not be converted")
        with monkeypatch.context() as patch:
            patch.setattr(module.np, "asarray", forbidden)
            assert worker.feed(oversized, sample_rate=48_000) is False
        assert worker._queue.empty()
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)


def test_worker_budget_boundary_preserves_short_valid_iq(monkeypatch, tmp_path):
    worker, release = _waiting_worker(monkeypatch, tmp_path)
    try:
        allowed = np.ones(module.MAX_WORKER_OUTPUT_SAMPLES, dtype=np.complex64)
        assert worker.feed(allowed, sample_rate=48_000) is True
        assert worker._queue.qsize() == 1
        assert worker.feed(np.ones(12_001, dtype=np.complex64),
                           sample_rate=48_000) is False
        assert worker.feed(np.ones(60_001, dtype=np.complex64),
                           sample_rate=240_000) is False
        assert worker._queue.qsize() == 1
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)


def test_worker_rejects_nested_oversized_iq_before_numpy_conversion(monkeypatch, tmp_path):
    worker, release = _waiting_worker(monkeypatch, tmp_path)
    try:
        # One outer element previously bypassed len() preflight despite
        # containing an arbitrarily large NumPy view.
        nested = [np.broadcast_to(np.complex64(1), (module.MAX_WORKER_INPUT_SAMPLES + 1,))]
        def forbidden(*args, **kwargs):
            raise AssertionError("nested IQ must be rejected before np.asarray")
        with monkeypatch.context() as patch:
            patch.setattr(module.np, "asarray", forbidden)
            assert worker.feed(nested, sample_rate=3_072_000) is False
        assert worker._queue.empty()
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)


def test_worker_rejects_multidimensional_ndarray_before_conversion(monkeypatch, tmp_path):
    worker, release = _waiting_worker(monkeypatch, tmp_path)
    try:
        matrix = np.ones((2, 2048), dtype=np.complex64)
        def forbidden(*args, **kwargs):
            raise AssertionError("IQ matrix must not be flattened on DSP thread")
        with monkeypatch.context() as patch:
            patch.setattr(module.np, "asarray", forbidden)
            assert worker.feed(matrix, sample_rate=48_000) is False
        assert worker._queue.empty()
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)


def test_worker_still_accepts_flat_numeric_iq_list(monkeypatch, tmp_path):
    worker, release = _waiting_worker(monkeypatch, tmp_path)
    try:
        assert worker.feed([1 + 2j] * 2048, sample_rate=48_000) is True
        assert worker._queue.qsize() == 1
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)
