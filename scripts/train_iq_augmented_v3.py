"""Augmented IQ classification candidate v3 (SYNTHETIC ONLY, never auto-deployed).

Shares the architecture and class ordering of the v2 model so comparisons of
the SAME fixed synthetic stress dataset are possible without confounding.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from iq_augmentation import augment_iq
from train_iq_synthetic_ci import CLASSES, Net, dataset, sample

TRAIN_SEED = 20261109
DATA_SEED = 71023


def augmented_dataset(count: int, seed: int, probability: float = 0.80):
    if count <= 0 or count % len(CLASSES) != 0:
        raise ValueError("Training sample count must be positive and class-balanced")
    rng = np.random.default_rng(seed)
    xs, ys = [], []
    for i in range(count):
        label = i % len(CLASSES)
        iq = sample(CLASSES[label], rng)
        if rng.random() < probability:
            iq = augment_iq(iq, rng)
        xs.append(iq)
        ys.append(label)
    return torch.from_numpy(np.stack(xs)), torch.tensor(ys)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-count", type=int, default=8400)
    parser.add_argument("--epochs", type=int, default=22)
    parser.add_argument("--output-dir", type=Path, default=Path("models/iq"))
    args = parser.parse_args()

    torch.set_num_threads(2)
    torch.manual_seed(TRAIN_SEED)
    np.random.seed(TRAIN_SEED)
    train_x, train_y = augmented_dataset(args.train_count, DATA_SEED)
    # Original v2 validation seed: comparable nominal benchmark, not RF validation.
    valid_x, valid_y = dataset(1400, 991)
    # A second clean seed provides an additional independent same-generator check.
    other_x, other_y = dataset(1400, 18739)

    model = Net()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.003)
    for epoch in range(args.epochs):
        model.train()
        for indices in torch.randperm(len(train_y)).split(128):
            optimizer.zero_grad()
            loss = nn.functional.cross_entropy(model(train_x[indices]), train_y[indices])
            loss.backward()
            optimizer.step()
        print(f"augmented epoch {epoch + 1}/{args.epochs}", flush=True)

    model.eval()

    def assess(x, y):
        with torch.no_grad():
            preds = torch.cat([model(batch).argmax(1) for batch in x.split(128)]).numpy()
        truth = y.numpy()
        confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=int)
        for actual, predicted in zip(truth, preds):
            confusion[actual, predicted] += 1
        return {
            "samples": int(len(y)),
            "accuracy": float(np.mean(preds == truth)),
            "confusion_matrix": confusion.tolist(),
            "per_class_recall": {
                name: float(confusion[i, i] / max(confusion[i].sum(), 1))
                for i, name in enumerate(CLASSES)
            },
        }

    report = {
        "labels": list(CLASSES),
        "training_samples": int(len(train_y)),
        "training_augmentation_probability": 0.8,
        "training_seed": TRAIN_SEED,
        "data_seed": DATA_SEED,
        "epochs": args.epochs,
        "architecture": "synthetic_v2 Net Conv1d unchanged",
        "validation_v2_seed": assess(valid_x, valid_y),
        "validation_holdout_seed": assess(other_x, other_y),
        "limitations": "Synthetic-only training and validation; no live RF/satellite data",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.output_dir / "synthetic_v3.pt")
    (args.output_dir / "synthetic_v3_metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
