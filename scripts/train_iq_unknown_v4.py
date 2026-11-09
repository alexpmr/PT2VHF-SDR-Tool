"""Experimental v4 training with broader UNKNOWN examples; never auto-deploy."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from iq_unknown_curriculum import FAMILIES, unknown_iq
from iq_augmentation import augment_iq
from train_iq_augmented_v3 import augmented_dataset
from train_iq_synthetic_ci import CLASSES, Net, dataset


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=22)
    p.add_argument("--train-count", type=int, default=8400)
    p.add_argument("--unknown-fraction", type=float, default=0.90,
                   help="Fraction of UNKNOWN training examples replaced with diverse synthetic negatives")
    p.add_argument("--model-stem", choices=("synthetic_v4", "synthetic_v5"),
                   default="synthetic_v4")
    p.add_argument("--output-dir", type=Path, default=Path("models/iq"))
    args = p.parse_args()
    if not (0 <= args.unknown_fraction <= 1):
        raise ValueError("unknown-fraction must be between zero and one")
    torch.set_num_threads(2)
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
        "unknown_families": FAMILIES,
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
