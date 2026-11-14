"""Fail-closed ONNX classifier threshold contract (synthetic stub, no RF)."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from pt2vhf.dsp.iq_classifier import IQClassifier


@pytest.fixture
def model_stub(monkeypatch, tmp_path):
    """Exercise the real constructor without ONNX binaries or network access."""
    class Session:
        def __init__(self, path, providers):
            assert providers == ["CPUExecutionProvider"]

        def get_inputs(self):
            return [SimpleNamespace(name="iq", shape=[1, 2, 2048])]

        def get_outputs(self):
            return [SimpleNamespace(name="logits", shape=[1, 7])]

    monkeypatch.setitem(
        sys.modules, "onnxruntime",
        SimpleNamespace(InferenceSession=Session),
    )
    model = tmp_path / "synthetic-stub.onnx"
    model.write_bytes(b"not an ONNX model; fake session only")
    return model


@pytest.mark.parametrize("threshold", [
    float("nan"), float("inf"), float("-inf"),
    np.float64(np.nan), -0.01, 1.01,
    True, False, np.bool_(True), "0.8", None, object(),
])
def test_classifier_rejects_invalid_confidence_gate(model_stub, threshold):
    """NaN used to silently turn every known prediction into UNKNOWN."""
    with pytest.raises(ValueError, match="min_confidence must be a finite number"):
        IQClassifier(model_stub, min_confidence=threshold)


@pytest.mark.parametrize("threshold", [
    0, 0.0, 0.8, 1, 1.0, np.float32(0.5), np.float64(0.75),
])
def test_classifier_preserves_valid_confidence_gate(model_stub, threshold):
    classifier = IQClassifier(model_stub, min_confidence=threshold)
    assert classifier.min_confidence == pytest.approx(float(threshold))
