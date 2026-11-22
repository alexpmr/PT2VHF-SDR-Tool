"""Evaluate exported IQ ONNX on independent synthetic and shifted inputs.

This is a diagnostic *synthetic-only* benchmark, NOT an RF accuracy claim.
The nominal threshold is a regression check; shifted cases intentionally have
no pass threshold so failures are captured in the JSON report for review.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier
from train_iq_synthetic_ci import sample

SEED = 20261111
FS = 48000
TRANSFORMS = ("nominal", "gain_phase", "dc_offset", "iq_imbalance",
              "cfo_350hz", "extra_noise_minus_5db")


def distort(iq: np.ndarray, condition: str, rng: np.random.Generator) -> np.ndarray:
    """Controlled perturbations; labels are kept only for observational diagnostics."""
    z = iq.astype(np.complex64, copy=True)
    if condition == "nominal":
        return z
    if condition == "gain_phase":
        return (z * np.complex64(0.4 * np.exp(1j * 1.37))).astype(np.complex64)
    if condition == "dc_offset":
        return (z + np.complex64(0.35 + 0.21j)).astype(np.complex64)
    if condition == "iq_imbalance":
        return (z.real + 1j * (0.78 * z.imag + 0.12 * z.real)).astype(np.complex64)
    if condition == "cfo_350hz":
        t = np.arange(z.size, dtype=np.float64) / FS
        return (z * np.exp(2j * np.pi * 350 * t)).astype(np.complex64)
    if condition == "extra_noise_minus_5db":
        noise = (rng.normal(size=z.size) + 1j * rng.normal(size=z.size)) / np.sqrt(2)
        rms = np.sqrt(np.mean(np.abs(z) ** 2))
        return (z + 10 ** (5 / 20) * rms * noise).astype(np.complex64)
    raise ValueError(f"Unrecognized synthetic perturbation: {condition}")


def evaluate(model_path: Path, per_class: int = 80) -> dict:
    if per_class < 1:
        raise ValueError("per_class must be positive")
    rng = np.random.default_rng(SEED)
    reference = []
    for label in CLASSES:
        for _ in range(per_class):
            iq = sample(label, rng)
            reference.append((label, (iq[0] + 1j * iq[1]).astype(np.complex64)))

    model = IQClassifier(model_path)
    reports = {}
    for idx, condition in enumerate(TRANSFORMS):
        # A fresh RNG makes every condition repeatable without changing the base signals.
        transform_rng = np.random.default_rng(SEED + idx + 1)
        confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=np.int64)
        confidences, timings = [], []
        rejected, correct_decisions = 0, 0
        for label, base in reference:
            iq = distort(base, condition, transform_rng)
            start = time.perf_counter()
            result = model.predict(iq)
            timings.append((time.perf_counter() - start) * 1000)
            predicted = max(result.probabilities, key=result.probabilities.get)
            confusion[CLASSES.index(label), CLASSES.index(predicted)] += 1
            confidences.append(result.confidence)
            rejected += result.mode == "UNKNOWN" and predicted != "UNKNOWN"
            correct_decisions += result.mode == label
        total = len(reference)
        report = {
            "samples": total,
            "top1_accuracy": float(np.trace(confusion) / total),
            "operational_accuracy_at_0_80": float(correct_decisions / total),
            "low_confidence_rejections": int(rejected),
            "mean_max_probability": float(np.mean(confidences)),
            "per_class_recall": {name: float(confusion[i, i] / per_class)
                                 for i, name in enumerate(CLASSES)},
            "confusion_matrix": confusion.tolist(),
            "inference_p50_ms": float(np.percentile(timings, 50)),
            "inference_p95_ms": float(np.percentile(timings, 95)),
        }
        reports[condition] = report
        print(f"{condition}: top1={report['top1_accuracy']:.3f}, "
              f"decision={report['operational_accuracy_at_0_80']:.3f}, "
              f"rejected={rejected}/{total}, p95={report['inference_p95_ms']:.2f} ms",
              flush=True)
    return {
        "scope": "Experimental synthetic-only perturbations; not independently recorded RF",
        "generator": "scripts/train_iq_synthetic_ci.py:sample",
        "seed": SEED,
        "class_order": list(CLASSES),
        "per_class": per_class,
        "min_confidence": 0.8,
        "units": "inference timings measured on CI machine; not hardware latency",
        "limitations": ("Training and evaluation use the same signal generator family; "
                        "AM/WFM synthesis and propagation are not representative of all RF channels. "
                        "Observed robustness does not establish on-air modulation classification."),
        "conditions": reports,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--per-class", type=int, default=80)
    args = p.parse_args()
    report = evaluate(args.model, per_class=args.per_class)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    # Regression criterion only for same-family, previously unseen, independent signals.
    nominal = report["conditions"]["nominal"]["top1_accuracy"]
    if nominal < 0.94:
        raise SystemExit(f"Nominal synthetic regression: accuracy={nominal:.3f} < 0.940")
    print(f"Diagnostic report saved: {args.output}", flush=True)


if __name__ == "__main__":
    main()
