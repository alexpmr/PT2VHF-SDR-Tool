"""Deterministic tests for the new, independent IQ test generator."""
import numpy as np
import pytest

from scripts.iq_out_of_family import NEGATIVES, SUPPORTED, N, negative, sample


@pytest.mark.parametrize("mode", SUPPORTED)
def test_independent_ood_generator_valid_and_repeatable(mode):
    a = sample(mode, np.random.default_rng(114), 9)
    b = sample(mode, np.random.default_rng(114), 9)
    np.testing.assert_array_equal(a, b)
    assert a.shape == (N,)
    assert a.dtype == np.complex64
    assert np.isfinite(a).all()
    assert np.sqrt(np.mean(np.abs(a) ** 2)) == pytest.approx(1, abs=1e-6)


@pytest.mark.parametrize("kind", NEGATIVES)
def test_unlabelled_negative_signals_are_finite(kind):
    x = negative(kind, np.random.default_rng(125))
    assert x.shape == (N,)
    assert np.isfinite(x).all()
    assert np.sqrt(np.mean(np.abs(x) ** 2)) == pytest.approx(1, abs=1e-6)


def test_confidence_calibration_error_function():
    from scripts.evaluate_iq_ood import ece
    assert ece(np.array([0.8, 0.8]), np.array([True, False])) == pytest.approx(0.3)
    assert ece(np.array([1.0, 1.0]), np.array([True, True])) == pytest.approx(0.0)


def test_generator_rejects_wfm_and_invalid_shapes():
    with pytest.raises(ValueError, match="Unsupported"):
        sample("WFM", np.random.default_rng(6), 10)
    with pytest.raises(ValueError, match="Unsupported"):
        sample("NFM", np.random.default_rng(6), 10, n=1024)
    with pytest.raises(ValueError, match="Unknown"):
        negative("not-a-test", np.random.default_rng(6))



def test_ood_metric_denominators_and_confidence_thresholds(monkeypatch, tmp_path):
    """A deterministic known-class-only model must expose its OOD false positives.

    Prevent a CI-green synthetic pipeline from hiding erroneous acceptance or
    silently changing the report denominators. No actual ONNX model required.
    """
    from types import SimpleNamespace
    from scripts import evaluate_iq_ood

    class AlwaysAM:
        def __init__(self, path, min_confidence=0.8):
            self.min_confidence = min_confidence

        def predict(self, iq):
            probabilities = {mode: 0.1 / 6 for mode in
                             ("CW", "AM", "NFM", "WFM", "USB", "LSB", "UNKNOWN")}
            probabilities["AM"] = 0.9
            return SimpleNamespace(mode="AM", confidence=0.9,
                                   probabilities=probabilities)

    monkeypatch.setattr(evaluate_iq_ood, "IQClassifier", AlwaysAM)
    report = evaluate_iq_ood.run(tmp_path / "v2.onnx", tmp_path / "v3.onnx",
                                 count_per_class_snr=1, negatives_per_kind=1)

    assert report["classes_not_evaluated"] == ["WFM"]
    for model in report["models"].values():
        assert model["labeled_samples"] == 4 * len(SUPPORTED)
        assert model["negative_samples"] == len(NEGATIVES)
        assert model["top1_accuracy"] == pytest.approx(1 / len(SUPPORTED))
        assert model["high_confidence_wrong_rate"] == pytest.approx(
            (len(SUPPORTED) - 1) / len(SUPPORTED))
        assert all(item["high_confidence_known_class_rate"] == 1.0
                   for item in model["negative_ood"].values())
        lo = model["confidence_threshold_analysis"]["0.8"]
        hi = model["confidence_threshold_analysis"]["0.95"]
        assert lo["known_samples"] == 4 * (len(SUPPORTED) - 1)
        assert lo["unknown_samples"] == 4
        assert lo["ood_samples"] == len(NEGATIVES)
        assert lo["ood_negative_misaccepted"] == 1.0
        assert lo["unknown_noise_misaccepted"] == 1.0
        assert lo["correct_known_accepted"] == pytest.approx(1 / (len(SUPPORTED) - 1))
        assert hi["ood_negative_misaccepted"] == 0.0
        assert hi["correct_known_accepted"] == 0.0


def test_ood_report_seed_is_configurable_and_reproducible(monkeypatch, tmp_path):
    """Independent holdout seeds must not silently change baseline results."""
    from types import SimpleNamespace
    from scripts import evaluate_iq_ood

    fingerprints = []

    class FingerprintModel:
        def __init__(self, path, min_confidence=0.8):
            pass

        def predict(self, iq):
            fingerprints.append(np.asarray(iq).tobytes())
            probabilities = {mode: 0.1 / 6 for mode in
                             ("CW", "AM", "NFM", "WFM", "USB", "LSB", "UNKNOWN")}
            probabilities["AM"] = 0.9
            return SimpleNamespace(mode="AM", confidence=0.9,
                                   probabilities=probabilities)

    monkeypatch.setattr(evaluate_iq_ood, "IQClassifier", FingerprintModel)
    def capture(seed):
        fingerprints.clear()
        report = evaluate_iq_ood.run(tmp_path / "v2.onnx", tmp_path / "v3.onnx",
                                     count_per_class_snr=1, negatives_per_kind=1,
                                     seed=seed)
        return report, fingerprints[:]

    baseline, baseline_samples = capture(evaluate_iq_ood.SEED)
    repeated, repeated_samples = capture(evaluate_iq_ood.SEED)
    alternate, alternate_samples = capture(20261113)
    assert baseline["seed"] == repeated["seed"] == evaluate_iq_ood.SEED
    assert alternate["seed"] == 20261113
    assert baseline_samples == repeated_samples
    assert baseline_samples != alternate_samples
    assert baseline["models"] == repeated["models"]


@pytest.mark.parametrize("confidence,mode,am_probability,error", [
    (0.1, "AM", 0.9, "confidence disagrees"),
    (0.9, "CW", 0.9, "decision disagrees"),
    (0.9, "AM", 0.8, "probability distribution"),
    (float("nan"), "AM", 0.9, "confidence disagrees"),
])
def test_ood_report_rejects_favorable_metrics_from_malformed_model_outputs(
        monkeypatch, tmp_path, confidence, mode, am_probability, error):
    """A model stub must not suppress OOD false accepts using stale confidence."""
    from types import SimpleNamespace
    from scripts import evaluate_iq_ood

    class MalformedModel:
        min_confidence = 0.8

        def __init__(self, path, min_confidence=0.8):
            self.min_confidence = min_confidence

        def predict(self, iq):
            probabilities = {label: 0.1 / 6 for label in
                             ("CW", "AM", "NFM", "WFM", "USB", "LSB", "UNKNOWN")}
            probabilities["AM"] = am_probability
            return SimpleNamespace(mode=mode, confidence=confidence,
                                   probabilities=probabilities)

    monkeypatch.setattr(evaluate_iq_ood, "IQClassifier", MalformedModel)
    with pytest.raises(ValueError, match=error):
        evaluate_iq_ood.run(tmp_path / "v2.onnx", tmp_path / "v3.onnx",
                            count_per_class_snr=1, negatives_per_kind=1)


@pytest.mark.parametrize("confidences,hits,bins", [
    ([float("nan")], [True], 10),
    ([], [], 10),
    ([0.9], [True], 0),
    ([0.9], [True, False], 10),
    ([1.2], [False], 10),
])
def test_ood_ece_rejects_invalid_inputs_instead_of_reporting_zero(
        confidences, hits, bins):
    from scripts.evaluate_iq_ood import ece
    with pytest.raises(ValueError, match="Invalid calibration"):
        ece(np.asarray(confidences), np.asarray(hits), bins=bins)
