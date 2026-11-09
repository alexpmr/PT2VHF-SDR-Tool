"""Blind out-of-family IQ holdout: v2/v3 on identical, separate synthetic signals.

No promotion thresholds on classification accuracy. A result may be very poor:
that is a finding, NOT a reason to hide the measurements. Not RF validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier
if __package__:
    from .iq_out_of_family import NEGATIVES, SUPPORTED, negative, sample
else:
    from iq_out_of_family import NEGATIVES, SUPPORTED, negative, sample

SNR_LEVELS_DB = (0, 6, 12, 20)
SEED = 20261112


def ece(confidences: np.ndarray, hits: np.ndarray, bins=10) -> float:
    """Expected calibration error on top-1 probabilities."""
    error = 0.0
    for j in range(bins):
        lo, hi = j / bins, (j + 1) / bins
        mask = (confidences >= lo) & (confidences <= hi if j == bins - 1 else confidences < hi)
        if np.any(mask):
            error += float(np.mean(mask)) * abs(float(np.mean(hits[mask])) - float(np.mean(confidences[mask])))
    return error


def run(reference_path: Path, candidate_path: Path, count_per_class_snr: int = 40, negatives_per_kind: int = 80, third_model_path: Path | None = None) -> dict:
    if min(count_per_class_snr, negatives_per_kind) < 1:
        raise ValueError("Sample counts must be positive")
    rng = np.random.default_rng(SEED)
    labeled = [(mode, snr, sample(mode, rng, snr))
               for snr in SNR_LEVELS_DB for mode in SUPPORTED for _ in range(count_per_class_snr)]
    unknown = [(kind, negative(kind, rng))
               for kind in NEGATIVES for _ in range(negatives_per_kind)]
    summary = {}
    models = [("v2", reference_path), ("v3", candidate_path)]
    if third_model_path is not None:
        models.append(("v4", third_model_path))
    for key, path in models:
        model = IQClassifier(path, min_confidence=0.80)
        by_snr, per_class = {}, {}
        all_probs, all_hits, all_wrong_high = [], [], []
        labeled_predictions, negative_predictions = [], []
        for snr in SNR_LEVELS_DB:
            confusion = np.zeros((len(SUPPORTED), len(CLASSES)), dtype=int)
            for truth, db, iq in labeled:
                if db != snr:
                    continue
                result = model.predict(iq)
                chosen = max(result.probabilities, key=result.probabilities.get)
                confidence = result.confidence
                confusion[SUPPORTED.index(truth), CLASSES.index(chosen)] += 1
                hit = chosen == truth
                all_probs.append(confidence)
                all_hits.append(hit)
                all_wrong_high.append(not hit and confidence >= 0.80)
                labeled_predictions.append((truth, chosen, confidence))
            correct = sum(confusion[SUPPORTED.index(label), CLASSES.index(label)]
                          for label in SUPPORTED)
            total = int(confusion.sum())
            by_snr[str(snr)] = {
                "top1_accuracy": correct / total,
                "per_class_recall": {
                    label: float(confusion[i, CLASSES.index(label)] / count_per_class_snr)
                    for i, label in enumerate(SUPPORTED)
                },
                "confusion_matrix_rows": list(SUPPORTED),
                "confusion_matrix_columns": list(CLASSES),
                "confusion_matrix": confusion.tolist(),
                "sample_count": total,
            }
        for label in SUPPORTED:
            per_class[label] = float(np.mean([by_snr[str(s)]["per_class_recall"][label]
                                               for s in SNR_LEVELS_DB]))
        negative_results = {}
        for kind in NEGATIVES:
            counts = {label: 0 for label in CLASSES}
            high = 0
            for candidate_kind, iq in unknown:
                if candidate_kind != kind:
                    continue
                result = model.predict(iq)
                counts[result.mode] += 1
                predicted_raw = max(result.probabilities, key=result.probabilities.get)
                negative_predictions.append((predicted_raw, result.confidence))
                high += int(result.mode != "UNKNOWN" and result.confidence >= 0.80)
            negative_results[kind] = {
                "samples": negatives_per_kind,
                "high_confidence_known_class_rate": high / negatives_per_kind,
                "decisions": counts,
            }
        probs = np.asarray(all_probs, dtype=float)
        hits = np.asarray(all_hits, dtype=bool)
        # A single confidence threshold cannot be assumed to solve OOD errors.
        # Quantify the trade-off without using the evaluation set to tune weights.
        known = [(truth, pred, conf) for truth, pred, conf in labeled_predictions if truth != "UNKNOWN"]
        unknown_labeled = [(pred, conf) for truth, pred, conf in labeled_predictions if truth == "UNKNOWN"]
        threshold_curve = {}
        for threshold in (0.80, 0.90, 0.95, 0.99, 0.999):
            def accept(pred, conf):
                return pred != "UNKNOWN" and conf >= threshold

            threshold_curve[f"{threshold:g}"] = {
                "correct_known_accepted": sum(
                    pred == truth and accept(pred, conf)
                    for truth, pred, conf in known) / len(known),
                "wrong_known_accepted": sum(
                    pred != truth and accept(pred, conf)
                    for truth, pred, conf in known) / len(known),
                "unknown_noise_misaccepted": sum(
                    accept(pred, conf) for pred, conf in unknown_labeled) / len(unknown_labeled),
                "ood_negative_misaccepted": sum(
                    accept(pred, conf) for pred, conf in negative_predictions) / len(negative_predictions),
                "known_samples": len(known),
                "unknown_samples": len(unknown_labeled),
                "ood_samples": len(negative_predictions),
            }
        summary[key] = {
            "confidence_threshold_analysis": threshold_curve,
            "by_snr_db": by_snr,
            "per_class_recall_over_snr": per_class,
            "top1_accuracy": float(np.mean(hits)),
            "high_confidence_wrong_rate": float(np.mean(all_wrong_high)),
            "expected_calibration_error_10_bins": ece(probs, hits),
            "negative_ood": negative_results,
            "labeled_samples": len(labeled),
            "negative_samples": len(unknown),
        }
        print(f"{key}: top1={summary[key]['top1_accuracy']:.3f}, "
              f"high-confidence wrong={summary[key]['high_confidence_wrong_rate']:.3f}, "
              f"calibration error={summary[key]['expected_calibration_error_10_bins']:.3f}",
              flush=True)
        for snr in SNR_LEVELS_DB:
            d = by_snr[str(snr)]
            print(f"  SNR {snr:2d} dB: accuracy={d['top1_accuracy']:.3f} "
                  f"recall={d['per_class_recall']}", flush=True)
        for kind, d in negative_results.items():
            print(f"  OOD {kind}: high-confidence false acceptance "
                  f"{d['high_confidence_known_class_rate']:.3f}", flush=True)
        for threshold, vals in threshold_curve.items():
            print(f"  confidence threshold={threshold}: legitimate accepted="
                  f"{vals['correct_known_accepted']:.3f}; "
                  f"unknown misaccepted={vals['unknown_noise_misaccepted']:.3f}; "
                  f"OOD misaccepted={vals['ood_negative_misaccepted']:.3f}", flush=True)
    return {
        "scope": "Out-of-family narrowband synthetic generation; no real IQ and no valid WFM evaluation",
        "seed": SEED,
        "snr_levels_db": list(SNR_LEVELS_DB),
        "count_per_class_snr": count_per_class_snr,
        "negative_per_kind": negatives_per_kind,
        "labels_evaluated": list(SUPPORTED),
        "classes_not_evaluated": ["WFM"],
        "generator": "scripts/iq_out_of_family.py; not used by v2/v3 training",
        "limitations": ("Narrowband samples only; CW can contain less than one Morse symbol "
                        "in 42.7 ms; UNKNOWN depends on selected noise family; "
                        "neither calibration nor accuracy generalizes to RF hardware"),
        "models": summary,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--third-model", type=Path)
    parser.add_argument("--per-class-snr", type=int, default=40)
    parser.add_argument("--per-negative", type=int, default=80)
    args = parser.parse_args()
    result = run(args.reference, args.candidate, args.per_class_snr, args.per_negative, args.third_model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    assert result["classes_not_evaluated"] == ["WFM"]
    assert all(m["labeled_samples"] > 0 for m in result["models"].values())
    print("Independent synthetic diagnostic report saved:", args.output, flush=True)


if __name__ == "__main__":
    main()
