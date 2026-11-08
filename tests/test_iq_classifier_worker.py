import time
import numpy as np
from pt2vhf.dsp.iq_classifier_worker import IQClassificationWorker

def test_worker_missing_model_reports_error(tmp_path):
    errors = []
    worker = IQClassificationWorker(tmp_path / "missing.onnx", lambda *_: None, errors.append)
    worker._thread.join(timeout=3)
    assert errors
    worker.stop()

def test_worker_rejects_short_iq(tmp_path):
    worker = IQClassificationWorker(tmp_path / "missing.onnx", lambda *_: None)
    assert not worker.feed(np.ones(100, dtype=np.complex64))
    worker.stop()
