"""Experimental v4 training with broader UNKNOWN examples; never auto-deploy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import torch
from torch import nn
from iq_unknown_curriculum import FAMILIES, unknown_iq
from iq_augmentation import augment_iq
from train_iq_augmented_v3 import augmented_dataset
from train_iq_synthetic_ci import CLASSES, Net, dataset


def configure_training_runtime(portable_cpu: bool) -> dict:
    """Select a controlled CPU experiment; not a cross-hardware guarantee."""
    if portable_cpu:
        required = {"ATEN_CPU_CAPABILITY": "default", "MKL_CBWR": "COMPATIBLE"}
        for name, value in required.items():
            if os.environ.get(name) != value:
                raise RuntimeError(f"Portable CPU training requires {name}={value} before importing torch")
        torch.set_num_threads(1)
        torch.backends.mkldnn.enabled = False
        torch.use_deterministic_algorithms(True)
    else:
        torch.set_num_threads(2)
    return {
        "portable_cpu": portable_cpu,
        "threads": torch.get_num_threads(),
        "mkldnn_enabled": torch.backends.mkldnn.enabled,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "aten_cpu_capability": os.environ.get("ATEN_CPU_CAPABILITY", ""),
        "mkl_cbwr": os.environ.get("MKL_CBWR", ""),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=22)
    p.add_argument("--portable-cpu", action="store_true",
                   help="Experimental cross-CPU determinism policy; requires pre-import environment")
    p.add_argument("--train-count", type=int, default=8400)
    p.add_argument("--unknown-fraction", type=float, default=0.90,
                   help="Fraction of UNKNOWN training examples replaced with diverse synthetic negatives")
    p.add_argument("--model-stem", choices=("synthetic_v4", "synthetic_v5"),
                   default="synthetic_v4")
    p.add_argument("--output-dir", type=Path, default=Path("models/iq"))
    args = p.parse_args()
    if not (0 <= args.unknown_fraction <= 1):
        raise ValueError("unknown-fraction must be between zero and one")
    training_cpu_policy = configure_training_runtime(args.portable_cpu)
    torch.manual_seed(20261113)
    np.random.seed(20261113)
    x, y = augmented_dataset(args.train_count, 71023)
    rng = np.random.default_rng(81371)
    unknown_index = CLASSES.index("UNKNOWN")
    replaced = 0
    for i in torch.where(y == unknown_index)[0].tolist():
        if rng.random() < args.unknown_fraction:
            z = unknown_iq(rng)
            if rng.random() < .65:
                z = augment_iq(z, rng)
            x[i] = torch.from_numpy(z)
            replaced += 1
    validation_x, validation_y = dataset(1400, 991)
    model = Net()
    # Diagnostics only: prove whether different runners generated identical
    # training tensors and identical initial weights BEFORE optimizer updates.
    data_digest = hashlib.sha256()
    data_digest.update(x.contiguous().numpy().tobytes())
    data_digest.update(y.contiguous().numpy().tobytes())
    initial_digest = hashlib.sha256()
    for parameter in model.parameters():
        initial_digest.update(parameter.detach().contiguous().numpy().tobytes())
    optimizer = torch.optim.Adam(model.parameters(), lr=.003)
    for epoch in range(args.epochs):
        model.train()
        for indices in torch.randperm(len(y)).split(128):
            optimizer.zero_grad()
            loss = nn.functional.cross_entropy(model(x[indices]), y[indices])
            loss.backward()
            optimizer.step()
        print(f"unknown curriculum epoch {epoch+1}/{args.epochs}",flush=True)
    model.eval()
    with torch.no_grad():
        pred = torch.cat([model(batch).argmax(1) for batch in validation_x.split(128)]).numpy()
    truth = validation_y.numpy()
    confusion = np.zeros((7,7), dtype=int)
    for actual, predicted in zip(truth,pred):
        confusion[actual,predicted] += 1
    metrics = {
        "labels": list(CLASSES), "train_samples": len(y),
        "unknown_examples_replaced": replaced,
        "unknown_fraction": args.unknown_fraction,
        "training_cpu_policy": training_cpu_policy,
        "unknown_families": FAMILIES,
        "training_input_sha256": data_digest.hexdigest(),
        "initial_parameters_sha256": initial_digest.hexdigest(),
        "validation_samples": len(validation_y),
        "validation_accuracy": float(np.mean(pred==truth)),
        "per_class_recall": {name:float(confusion[i,i]/max(confusion[i].sum(),1))
                             for i,name in enumerate(CLASSES)},
        "confusion_matrix": confusion.tolist(),
        "limitations": "Synthetic labels are ambiguous; not validated on live RF"}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    torch.save(model.state_dict(),args.output_dir/f"{args.model_stem}.pt")
    (args.output_dir/f"{args.model_stem}_metrics.json").write_text(
        json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(metrics,indent=2),flush=True)


if __name__=="__main__":
    main()
