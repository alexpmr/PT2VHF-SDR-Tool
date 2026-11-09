"""Regression tests for IQ preprocessing and ONNX inference failure modes."""
import numpy as np
import pytest

from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier, SAMPLES


def _classifier_with_logits(output, threshold=0.8):
    # Model session double permits unit tests without shipping an ONNX binary.
    class FakeSession:
        def run(self, names, feeds):
            assert len(feeds["iq"].shape) == 3
            return [output]

    model = IQClassifier.__new__(IQClassifier)
    model.session = FakeSession()
    model.input_name = "iq"
    model.min_confidence = threshold
    return model


def _carrier():
    n = np.arange(SAMPLES, dtype=np.float32)
    return np.exp(2j * np.pi * 25 * n / SAMPLES).astype(np.complex64)


def test_features_invariant_to_gain_and_dc_offset():
    iq = _carrier()
    expected = IQClassifier.features(iq)
    actual = IQClassifier.features(iq * 3 + (7 + 2j))
    np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=2e-5)


def test_preprocessing_takes_center_window():
    carrier = _carrier()
    signal = np.concatenate([np.ones(16, np.complex64), carrier, np.full(16, -1, np.complex64)])
    np.testing.assert_allclose(IQClassifier.features(signal), IQClassifier.features(carrier), atol=1e-6)


def test_softmax_probability_contract_and_high_confidence():
    model = _classifier_with_logits(np.array([[12, 0, 0, 0, 0, 0, 0]], dtype="float32"))
    result = model.predict(_carrier())
    assert result.mode == CLASSES[0]
    assert result.confidence > 0.99
    assert set(result.probabilities) == set(CLASSES)
    assert sum(result.probabilities.values()) == pytest.approx(1.0)


def test_low_confidence_rejects_without_fabricating_mode():
    model = _classifier_with_logits(np.zeros((1, 7), dtype="float32"))
    result = model.predict(_carrier())
    assert result.mode == "UNKNOWN"
    assert result.confidence == pytest.approx(1 / 7)
    assert sum(result.probabilities.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("invalid", [
    np.zeros((1, 8), dtype="float32"),
    np.array([[np.nan] * 7], dtype="float32"),
    np.array([[np.inf] * 7], dtype="float32"),
])
def test_invalid_model_output_rejected(invalid):
    model = _classifier_with_logits(invalid)
    with pytest.raises(ValueError, match="Invalid model output"):
        model.predict(_carrier())


def test_too_short_and_nonfinite_iq_are_rejected():
    with pytest.raises(ValueError, match="Insufficient IQ"):
        IQClassifier.features(np.ones(SAMPLES - 1, dtype=np.complex64))
    samples = _carrier()
    samples[-1] = np.inf
    with pytest.raises(ValueError, match="Non-finite"):
        IQClassifier.features(samples)
