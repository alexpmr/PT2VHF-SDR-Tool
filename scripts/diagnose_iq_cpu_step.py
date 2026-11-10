"""Cheap synthetic one-optimizer-step probe for cross-CPU numerical divergence.

Not a full training run, not a model export, and never RF validation.
"""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path

import numpy as np
import torch
from torch import nn

from train_iq_augmented_v3 import augmented_dataset
from train_iq_synthetic_ci import Net
from train_iq_unknown_v4 import configure_training_runtime


def sha_tensors(tensors):
    h = hashlib.sha256()
    for tensor in tensors:
        h.update(tensor.detach().contiguous().cpu().numpy().tobytes())
    return h.hexdigest()


def run_probe():
    policy = configure_training_runtime(True)
    torch.manual_seed(20261113)
    np.random.seed(20261113)
    # A small representative synthetic batch, NOT the full 8,400-sample v4 run.
    x, y = augmented_dataset(128, 71023)
    model = Net()
    optimizer = torch.optim.Adam(model.parameters(), lr=.003)
    record = {
        "scope": "Synthetic 128-sample single Adam step; not full v4 replay or RF",
        "cpu_model": next((line.partition(":")[2].strip() for line in
                           Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), "unknown"),
        "cpu_capability": torch.backends.cpu.get_cpu_capability(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "policy": policy,
        "input_sha256": sha_tensors([x, y]),
        "initial_parameters_sha256": sha_tensors(model.parameters()),
    }
    logits = model(x)
    record["forward_logits_sha256"] = sha_tensors([logits])
    loss = nn.functional.cross_entropy(logits, y)
    record["loss_sha256"] = sha_tensors([loss])
    optimizer.zero_grad()
    loss.backward()
    record["gradients_sha256"] = sha_tensors(
        [p.grad for p in model.parameters()])
    optimizer.step()
    record["updated_parameters_sha256"] = sha_tensors(model.parameters())
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
