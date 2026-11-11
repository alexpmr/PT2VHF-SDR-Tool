"""Reproduce the first four optimizer steps of synthetic v4, not full training/RF."""
import argparse
import copy
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch
from torch import nn

from iq_augmentation import augment_iq
from iq_unknown_curriculum import unknown_iq
from train_iq_augmented_v3 import augmented_dataset
from train_iq_synthetic_ci import CLASSES, Net, dataset
from train_iq_unknown_v4 import configure_training_runtime


def sha_tensors(tensors):
    h = hashlib.sha256()
    for t in tensors:
        h.update(t.detach().contiguous().cpu().numpy().tobytes())
    return h.hexdigest()


def conv1d_scalar_samples(inputs, layer, outputs, sample_count=32):
    """Sample native Conv1d versus a scalar float64 reference (diagnostic only)."""
    if not isinstance(layer, nn.Conv1d) or layer.groups != 1 or layer.padding_mode != "zeros":
        raise ValueError("Only zero-padded, ungrouped Conv1d is supported")
    if inputs.ndim != 3 or outputs.ndim != 3:
        raise ValueError("Conv1d expects [batch, channels, time]")
    total = outputs.numel()
    count = min(sample_count, total)
    if count < 1:
        raise ValueError("Cannot sample an empty convolution output")
    positions = [0] if count == 1 else [j * (total - 1) // (count - 1) for j in range(count)]
    x = inputs.detach().cpu()
    w = layer.weight.detach().cpu()
    bias = layer.bias.detach().cpu() if layer.bias is not None else None
    y = outputs.detach().cpu()
    stride, padding, dilation = layer.stride[0], layer.padding[0], layer.dilation[0]
    observed, reference = [], []
    for pos in positions:
        t = pos % y.shape[2]
        channel = (pos // y.shape[2]) % y.shape[1]
        batch = pos // (y.shape[1] * y.shape[2])
        acc = float(bias[channel]) if bias is not None else 0.0
        for ic in range(x.shape[1]):
            for k in range(w.shape[2]):
                ix = t * stride - padding + k * dilation
                if 0 <= ix < x.shape[2]:
                    acc += float(x[batch, ic, ix]) * float(w[channel, ic, k])
        observed.append(float(y[batch, channel, t]))
        reference.append(acc)
    errors = [abs(a - b) for a, b in zip(observed, reference)]
    return {"sample_count": count, "observed": observed, "reference": reference,
            "max_abs_error": max(errors), "mean_abs_error": sum(errors) / count}


def conv1d_float64_reference(inputs, layer, outputs):
    """Full-tensor float64 Conv1d control for the first synthetic minibatch.

    This is diagnostic only: it does not change model training or inference.
    A matching hash across CPUs tests the precision hypothesis; it does not
    prove the float32 training is reproducible.
    """
    if not isinstance(layer, nn.Conv1d) or layer.groups != 1 or layer.padding_mode != "zeros":
        raise ValueError("Only zero-padded, ungrouped Conv1d is supported")
    with torch.no_grad():
        x = inputs.detach().cpu().to(dtype=torch.float64)
        w = layer.weight.detach().cpu().to(dtype=torch.float64)
        bias = (layer.bias.detach().cpu().to(dtype=torch.float64)
                if layer.bias is not None else None)
        reference = nn.functional.conv1d(
            x, w, bias, stride=layer.stride, padding=layer.padding,
            dilation=layer.dilation, groups=layer.groups)
        observed = outputs.detach().cpu().to(dtype=torch.float64)
        if reference.shape != observed.shape or not reference.numel():
            raise ValueError("Invalid Conv1d output shape")
        error = (reference - observed).abs()
        return {
            "reference_sha256": sha_tensors([reference]),
            "max_abs_error": float(error.max().item()),
            "mean_abs_error": float(error.mean().item()),
        }


def float64_first_optimizer_step(model, batch_x, batch_y):
    """Isolated double-precision forward/backward/Adam control; no model mutation."""
    replica = copy.deepcopy(model).double()
    optimizer = torch.optim.Adam(replica.parameters(), lr=.003)
    result = {"initial_parameters_sha256": sha_tensors(replica.parameters())}
    optimizer.zero_grad()
    logits = replica(batch_x.double())
    result["forward_logits_sha256"] = sha_tensors([logits])
    loss = nn.functional.cross_entropy(logits, batch_y)
    result["loss_sha256"] = sha_tensors([loss])
    loss.backward()
    result["gradients_sha256"] = sha_tensors([weight.grad for weight in replica.parameters()])
    optimizer.step()
    result["updated_parameters_sha256"] = sha_tensors(replica.parameters())
    return result


def run_probe(steps=4):
    if not 1 <= steps <= 66:
        raise ValueError("steps must be between 1 and 66")
    policy = configure_training_runtime(True)
    torch.manual_seed(20261113)
    np.random.seed(20261113)
    x, y = augmented_dataset(8400, 71023)
    rng = np.random.default_rng(81371)
    replaced = 0
    for i in torch.where(y == CLASSES.index("UNKNOWN"))[0].tolist():
        if rng.random() < .90:
            z = unknown_iq(rng)
            if rng.random() < .65:
                z = augment_iq(z, rng)
            x[i] = torch.from_numpy(z)
            replaced += 1
    valid_x, valid_y = dataset(1400, 991)
    model = Net()
    optimizer = torch.optim.Adam(model.parameters(), lr=.003)
    cpuinfo = Path("/proc/cpuinfo")
    cpu = next((line.partition(":")[2].strip() for line in
                cpuinfo.read_text().splitlines()
                if line.startswith("model name")), "unknown") if cpuinfo.exists() else "unknown"
    report = {
        "scope": "First four v4 synthetic optimizer steps; NOT full training or RF",
        "cpu_model": cpu, "cpu_capability": torch.backends.cpu.get_cpu_capability(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__, "numpy_version": np.__version__,
        "policy": policy, "train_samples": len(y),
        "unknown_examples_replaced": replaced, "requested_steps": steps,
        "input_sha256": sha_tensors([x, y]),
        "validation_input_sha256": sha_tensors([valid_x, valid_y]),
        "initial_parameters_sha256": sha_tensors(model.parameters()),
        "steps": [],
    }
    model.train()
    indices_all = torch.randperm(len(y))
    report["epoch0_permutation_sha256"] = sha_tensors([indices_all])
    for i, indices in enumerate(indices_all.split(128)):
        if i >= steps:
            break
        batch_x, batch_y = x[indices], y[indices]
        item = {"step": i, "indices_sha256": sha_tensors([indices]),
                "batch_sha256": sha_tensors([batch_x, batch_y])}
        if i == 0:
            item["float64_first_step"] = float64_first_optimizer_step(model, batch_x, batch_y)
        optimizer.zero_grad()
        # Forward through the same nn.Sequential, hashing each intermediate
        # tensor before any backward/Adam operation. No model semantics change.
        activations = batch_x
        layer_hashes = {}
        for layer_index, layer in enumerate(model.net):
            layer_input = activations
            activations = layer(activations)
            layer_hashes[f"{layer_index:02d}_{type(layer).__name__}"] = sha_tensors([activations])
            if i == 0 and layer_index == 0:
                item["first_conv_scalar_samples"] = conv1d_scalar_samples(
                    layer_input, layer, activations)
            if i == 0 and layer_index == 2:
                item["second_conv_scalar_samples"] = conv1d_scalar_samples(
                    layer_input, layer, activations)
                item["second_conv_float64_reference"] = conv1d_float64_reference(
                    layer_input, layer, activations)
        item["layer_forward_sha256"] = layer_hashes
        logits = activations
        item["forward_logits_sha256"] = sha_tensors([logits])
        loss = nn.functional.cross_entropy(logits, batch_y)
        item["loss_sha256"] = sha_tensors([loss])
        loss.backward()
        item["gradients_sha256"] = sha_tensors([p.grad for p in model.parameters()])
        optimizer.step()
        item["updated_parameters_sha256"] = sha_tensors(model.parameters())
        report["steps"].append(item)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--steps", type=int, default=4)
    args = p.parse_args()
    report = run_probe(args.steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
