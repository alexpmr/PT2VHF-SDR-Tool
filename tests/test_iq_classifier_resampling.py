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
