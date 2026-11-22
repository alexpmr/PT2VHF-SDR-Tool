"""Export the synthetic v2 checkpoint to ONNX and verify numerical parity.

Run: python scripts/export_iq_synthetic_v2.py --checkpoint synthetic_v2.pt --output synthetic_v2.onnx
Requires torch, onnx and onnxruntime. This is an EXPERIMENTAL synthetic model.
"""
import argparse
from pathlib import Path
import numpy as np
import torch
from torch import nn

ONNX_OPSET = 18  # PyTorch's current exporter emits 18; avoid failed 17 down-conversion.

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(2,24,9,stride=4,padding=4), nn.ReLU(),
            nn.Conv1d(24,48,7,stride=4,padding=3), nn.ReLU(),
            nn.Conv1d(48,64,5,stride=4,padding=2), nn.ReLU(),
            nn.Conv1d(64,64,5,stride=2,padding=2), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(64,7))

    def forward(self, x):
        return self.net(x)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    import onnx
    import onnxruntime as ort
    model = Net()
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    rng = np.random.default_rng(20261109)
    example = torch.from_numpy(rng.normal(size=(1,2,2048)).astype("float32"))
    with torch.no_grad():
        torch.onnx.export(model, example, str(args.output), input_names=["iq"],
                          output_names=["logits"], opset_version=ONNX_OPSET)
    model_proto = onnx.load(str(args.output))
    onnx.checker.check_model(model_proto)
    exported_opsets = {item.domain: item.version for item in model_proto.opset_import}
    actual_opset = exported_opsets.get("", exported_opsets.get("ai.onnx"))
    if actual_opset != ONNX_OPSET:
        raise RuntimeError(f"Unexpected ONNX opset: requested {ONNX_OPSET}, found {actual_opset}")
    session = ort.InferenceSession(str(args.output), providers=["CPUExecutionProvider"])
    if session.get_inputs()[0].shape != [1, 2, 2048]:
        raise RuntimeError(f"Unexpected ONNX input shape: {session.get_inputs()[0].shape}")
    if session.get_outputs()[0].shape != [1, 7]:
        raise RuntimeError(f"Unexpected ONNX output shape: {session.get_outputs()[0].shape}")
    errors = []
    # Verify both arbitrary tensors and examples from each signal class.
    from train_iq_synthetic_ci import CLASSES, sample
    samples = [rng.normal(size=(1, 2, 2048)).astype("float32") for _ in range(10)]
    samples.extend(sample(label, rng)[None] for label in CLASSES for _ in range(3))
    for data in samples:
        with torch.no_grad():
            expected = model(torch.from_numpy(data)).numpy()
        actual = session.run(None, {"iq": data})[0]
        errors.append(float(np.max(np.abs(expected - actual))))
    max_error = max(errors)
    if max_error > 1e-4:
        raise RuntimeError(f"ONNX parity failed: max error {max_error}")
    print(f"ONNX opset {ONNX_OPSET} validated: {args.output}; {len(samples)} parity cases; max absolute error={max_error:.8f}")

if __name__ == "__main__":
    main()
