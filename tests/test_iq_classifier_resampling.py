import threading
import numpy as np
from scipy.signal import resample_poly
from pt2vhf.dsp import iq_classifier_worker as module


def _capture_input(monkeypatch, tmp_path, iq, fs):
    captured = []
    completed = threading.Event()

    class StubClassifier:
        def __init__(self, *args, **kwargs):
            pass
        def predict(self, samples):
            captured.append(samples.copy())
            completed.set()
            return "test-result"

    monkeypatch.setattr(module, "IQClassifier", StubClassifier)
    worker = module.IQClassificationWorker(tmp_path / "unused.onnx", lambda *_: None)
    try:
        assert worker.feed(iq, sample_rate=fs)
        assert completed.wait(timeout=5), "Inference worker did not process IQ"
        return captured[0]
    finally:
        worker.stop()


def test_240khz_if_resampled_to_48khz(monkeypatch, tmp_path):
    fs = 240000
    t = np.arange(24000) / fs
    iq = np.exp(2j * np.pi * 1000 * t).astype(np.complex64)
    actual = _capture_input(monkeypatch, tmp_path, iq, fs)
    assert actual.size == 4800
    np.testing.assert_allclose(actual, resample_poly(iq, 1, 5), atol=1e-6)


def test_native_48khz_not_resampled(monkeypatch, tmp_path):
    iq = np.ones(4096, dtype=np.complex64)
    actual = _capture_input(monkeypatch, tmp_path, iq, 48000)
    np.testing.assert_array_equal(actual, iq)


def test_resampling_is_offloaded_from_sdr_feed_thread(monkeypatch, tmp_path):
    """Synthetic regression: polyphase FIR must run on the worker thread."""
    from scipy import signal

    calls = []
    original = signal.resample_poly

    def traced(*args, **kwargs):
        calls.append(threading.current_thread().name)
        return original(*args, **kwargs)

    monkeypatch.setattr(signal, "resample_poly", traced)
    samples = np.ones(24000, dtype=np.complex64)
    result = _capture_input(monkeypatch, tmp_path, samples, 240000)
    assert result.size == 4800
    assert calls == ["iq-classifier"]


def test_feed_rejects_invalid_resampling_rates_and_short_output(tmp_path):
    """Invalid/unsafe ratios and undersized output must not reach inference."""
    worker = module.IQClassificationWorker(tmp_path / "unused.onnx",
                                            lambda *_: None)
    try:
        samples = np.ones(4096, dtype=np.complex64)
        for rate in (0, -1, float("nan"), float("inf"), 48000.5,
                     None, "invalid", 1):
            assert not worker.feed(samples, sample_rate=rate)
        assert not worker.feed(samples[:2048], sample_rate=240000)
        assert worker._queue.empty()
    finally:
        worker.stop()
