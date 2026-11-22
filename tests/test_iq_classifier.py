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



@pytest.mark.parametrize("carrier", [
    np.complex64(.3+.2j), np.complex64(.03+.04j),
    np.complex64(.7+.1j), np.complex64(.1+0j),
])
def test_dc_only_never_normalized_into_artificial_iq(carrier):
    samples = np.full(SAMPLES, carrier, dtype=np.complex64)
    with pytest.raises(ValueError, match="No usable RF signal"):
        IQClassifier.features(samples)


def test_numerical_noise_after_dc_removal_is_not_mistaken_for_rf():
    t = np.arange(SAMPLES, dtype=np.float64) / 48000
    tiny = 1e-7 * np.exp(2j*np.pi*1300*t)
    iq = (np.complex64(.3+.2j) + tiny).astype(np.complex64)
    with pytest.raises(ValueError, match="No usable RF signal"):
        IQClassifier.features(iq)


def test_modulated_centered_am_still_has_valid_model_features():
    t = np.arange(SAMPLES, dtype=np.float64) / 48000
    iq = (.3*(1 + .2*np.sin(2*np.pi*750*t)) *
          np.exp(.25j)).astype(np.complex64)
    features = IQClassifier.features(iq)
    z = features[0,0] + 1j*features[0,1]
    assert np.isfinite(features).all()
    assert abs(z.mean()) < 1e-4
    assert np.isclose(np.sqrt(np.mean(abs(z)**2)),1,atol=1e-4)

@pytest.mark.parametrize("gain", [1e20, 1e30, 3e38])
def test_extreme_finite_iq_gain_does_not_overflow_to_fake_zero_features(gain):
    """Synthetic numerical regression; this is not RF model validation."""
    n = np.arange(SAMPLES, dtype=np.float64)
    carrier = np.exp(2j * np.pi * 7 * n / SAMPLES).astype(np.complex64)
    reference = IQClassifier.features(carrier)
    amplified = IQClassifier.features(carrier * np.complex64(gain))
    assert amplified.shape == reference.shape
    assert np.isfinite(amplified).all()
    np.testing.assert_allclose(amplified, reference, rtol=2e-5, atol=2e-5)
    assert float(np.max(np.abs(amplified))) > 0.5


def test_extreme_finite_dc_only_remains_rejected():
    """Overflow fallback must not invent RF from an enormous DC offset."""
    carrier = np.full(SAMPLES, np.complex64(3e38), dtype=np.complex64)
    with pytest.raises(ValueError, match="No usable RF signal"):
        IQClassifier.features(carrier)
