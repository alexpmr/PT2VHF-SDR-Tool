import numpy as np
import pytest
from pt2vhf.dsp.iq_classifier import IQClassifier, SAMPLES

def test_missing_model_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        IQClassifier(tmp_path / "missing.onnx")

def test_preprocessing_shape_and_finiteness():
    x = np.exp(2j * np.pi * np.arange(4096) / 19).astype(np.complex64)
    features = IQClassifier.features(x)
    assert features.shape == (1, 2, SAMPLES)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()

def test_silence_is_rejected():
    with pytest.raises(ValueError):
        IQClassifier.features(np.zeros(SAMPLES, np.complex64))

def test_nonfinite_is_rejected():
    x = np.ones(SAMPLES, np.complex64)
    x[0] = np.nan
    with pytest.raises(ValueError):
        IQClassifier.features(x)
