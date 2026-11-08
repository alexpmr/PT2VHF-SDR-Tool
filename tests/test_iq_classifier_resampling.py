import numpy as np
from scipy.signal import resample_poly
from pt2vhf.dsp.iq_classifier_worker import IQClassificationWorker


def test_240khz_if_resampled_to_48khz(tmp_path):
    worker = IQClassificationWorker(tmp_path / "missing.onnx", lambda *_: None)
    # Input: 0.1 second at 240 kHz -> 4,800 samples at 48 kHz.
    fs = 240000
    t = np.arange(24000) / fs
    iq = np.exp(2j * np.pi * 1000 * t).astype(np.complex64)
    assert worker.feed(iq, sample_rate=fs)
    queued, _, _ = worker._queue.get_nowait()
    assert queued.size == 4800
    expected = resample_poly(iq, 1, 5)
    np.testing.assert_allclose(queued, expected, atol=1e-6)
    worker.stop()


def test_native_48khz_not_resampled(tmp_path):
    worker = IQClassificationWorker(tmp_path / "missing.onnx", lambda *_: None)
    iq = np.ones(4096, dtype=np.complex64)
    assert worker.feed(iq, sample_rate=48000)
    queued, _, _ = worker._queue.get_nowait()
    np.testing.assert_array_equal(queued, iq)
    worker.stop()
