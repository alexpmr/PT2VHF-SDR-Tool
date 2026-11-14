"""Fail-closed ONNX metadata checks; synthetic runtime stubs, no RF/weights."""
import sys
from types import SimpleNamespace

import pytest

from pt2vhf.dsp.iq_classifier import IQClassifier


def _load_with_metadata(monkeypatch, tmp_path, input_shape, input_type,
                        output_shape, output_type):
    class Session:
        def __init__(self, path, providers):
            assert providers == ["CPUExecutionProvider"]

        def get_inputs(self):
            return [SimpleNamespace(name="iq", shape=input_shape, type=input_type)]

        def get_outputs(self):
            return [SimpleNamespace(name="logits", shape=output_shape, type=output_type)]

        def run(self, *_args, **_kwargs):
            pytest.fail("Metadata validation must not perform inference")

    monkeypatch.setitem(
        sys.modules, "onnxruntime", SimpleNamespace(InferenceSession=Session)
    )
    path = tmp_path / "metadata-stub.onnx"
    path.write_bytes(b"synthetic test stub, not a trained model")
    return IQClassifier(path)


@pytest.mark.parametrize("batch", [1, None, "batch"])
def test_valid_float32_onnx_contract_accepts_fixed_or_dynamic_batch(
    monkeypatch, tmp_path, batch
):
    model = _load_with_metadata(
        monkeypatch, tmp_path, [batch, 2, 2048], "tensor(float)",
        [batch, 7], "tensor(float)"
    )
    assert model.input_name == "iq"
    assert model.min_confidence == 0.8


@pytest.mark.parametrize(("input_shape", "input_type", "output_shape",
                          "output_type", "message"), [
    ([2, 2, 2048], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([1, 2048, 2], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([1, 2, 1024], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([1, 2, 2048, 1], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([True, 2, 2048], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([1, True, 2048], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([1, "channels", 2048], "tensor(float)", [1, 7], "tensor(float)", "input shape"),
    ([1, 2, 2048], "tensor(double)", [1, 7], "tensor(float)", "float32 IQ"),
    ([1, 2, 2048], "tensor(float16)", [1, 7], "tensor(float)", "float32 IQ"),
    ([1, 2, 2048], "tensor(float)", [1, 6], "tensor(float)", "output shape"),
    ([1, 2, 2048], "tensor(float)", [2, 7], "tensor(float)", "output shape"),
    ([1, 2, 2048], "tensor(float)", [1, 7, 1], "tensor(float)", "output shape"),
    ([1, 2, 2048], "tensor(float)", [1, True], "tensor(float)", "output shape"),
    ([1, 2, 2048], "tensor(float)", [1, 7], "tensor(double)", "float32 logits"),
    ([1, 2, 2048], "tensor(float)", [1, 7], "tensor(float16)", "float32 logits"),
])
def test_invalid_onnx_contract_rejected_before_first_inference(
    monkeypatch, tmp_path, input_shape, input_type, output_shape,
    output_type, message
):
    with pytest.raises(ValueError, match=message):
        _load_with_metadata(
            monkeypatch, tmp_path, input_shape, input_type,
            output_shape, output_type
        )
