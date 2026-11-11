import time
import numpy as np
from pt2vhf.dsp.iq_classifier_worker import IQClassificationWorker

def test_worker_missing_model_reports_error(tmp_path):
    errors = []
    worker = IQClassificationWorker(tmp_path / "missing.onnx", lambda *_: None, errors.append)
    worker._thread.join(timeout=3)
    assert errors
    assert not worker.feed(np.ones(4096, dtype=np.complex64))
    worker.stop()

def test_worker_rejects_short_iq(tmp_path):
    worker = IQClassificationWorker(tmp_path / "missing.onnx", lambda *_: None)
    assert not worker.feed(np.ones(100, dtype=np.complex64))
    worker.stop()


def test_worker_rejects_malformed_iq_without_raising(monkeypatch, tmp_path):
    from pt2vhf.dsp import iq_classifier_worker as module

    class StubClassifier:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, samples):
            return "unused"

    monkeypatch.setattr(module, "IQClassifier", StubClassifier)
    worker = module.IQClassificationWorker(tmp_path / "unused.onnx", lambda *_: None)
    try:
        for invalid in ("not-complex", object(), [["bad", 1]]):
            assert worker.feed(invalid) is False
        assert worker._queue.empty()
    finally:
        worker.stop()


def test_worker_queue_replacement_race_does_not_escape_feed(monkeypatch, tmp_path):
    import queue
    import threading
    from pt2vhf.dsp import iq_classifier_worker as module

    started = threading.Event()
    release = threading.Event()

    class WaitingClassifier:
        def __init__(self, *args, **kwargs):
            started.set()
            release.wait(timeout=5)

        def predict(self, samples):
            return "unused"

    class ConcurrentQueue:
        def put_nowait(self, item):
            raise queue.Full

        def get_nowait(self):
            return "old-item"

        def get(self, timeout=None):
            raise queue.Empty

    monkeypatch.setattr(module, "IQClassifier", WaitingClassifier)
    worker = module.IQClassificationWorker(tmp_path / "unused.onnx", lambda *_: None)
    try:
        assert started.wait(timeout=2)
        worker._queue = ConcurrentQueue()
        assert worker.feed(np.ones(4096, dtype=np.complex64)) is False
        assert worker.dropped == 1
    finally:
        release.set()
        worker.stop()
        worker._thread.join(timeout=2)


def test_worker_fails_closed_when_error_handler_raises(monkeypatch, tmp_path):
    from pt2vhf.dsp import iq_classifier_worker as module

    class FailingClassifier:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, samples):
            raise ValueError("synthetic inference failure")

    def broken_error_handler(message):
        raise RuntimeError("synthetic callback failure")

    monkeypatch.setattr(module, "IQClassifier", FailingClassifier)
    worker = module.IQClassificationWorker(
        tmp_path / "unused.onnx", lambda *_: None, broken_error_handler
    )
    try:
        assert worker.feed(np.ones(4096, dtype=np.complex64))
        worker._thread.join(timeout=3)
        assert not worker._thread.is_alive()
        assert worker._stop.is_set()
        assert not worker.feed(np.ones(4096, dtype=np.complex64))
    finally:
        worker.stop()
