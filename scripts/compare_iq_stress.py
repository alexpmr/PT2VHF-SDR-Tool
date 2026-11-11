"""Compare v2 baseline vs augmented v3 on IDENTICAL independent synthetic IQ.

No automatic model promotion; tests are diagnostic and RF confirmation is mandatory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


MEASURES = ("top1_accuracy", "operational_accuracy_at_0_80",
            "low_confidence_rejections", "inference_p95_ms")


def compare(reference: dict, candidate: dict) -> dict:
    if reference["seed"] != candidate["seed"] or reference["per_class"] != candidate["per_class"]:
        raise ValueError("Comparison datasets/seeds differ")
    if reference["class_order"] != candidate["class_order"]:
        raise ValueError("Class orders differ")
    if set(reference["conditions"]) != set(candidate["conditions"]):
        raise ValueError("Stress scenarios differ")
    scenarios = {}
    for name in reference["conditions"]:
        a, b = reference["conditions"][name], candidate["conditions"][name]
        if a["samples"] != b["samples"]:
            raise ValueError(f"Sample sizes differ for {name}")
        scenarios[name] = {
            "reference": {k: a[k] for k in MEASURES},
            "candidate": {k: b[k] for k in MEASURES},
            "delta_top1_percentage_points": 100 * (b["top1_accuracy"] - a["top1_accuracy"]),
            "delta_operational_percentage_points": 100 * (
                b["operational_accuracy_at_0_80"] - a["operational_accuracy_at_0_80"]),
            "candidate_per_class_recall": b["per_class_recall"],
        }
    ref = reference["conditions"]
    cand = candidate["conditions"]
    return {
        "scope": "Controlled comparison on same-generator synthetic-only stress inputs",
        "reference": "synthetic_v2",
        "candidate": "synthetic_v3",
        "seed": reference["seed"],
        "samples_per_scenario": next(iter(ref.values()))["samples"],
        "conditions": scenarios,
        "criteria": {
            "candidate_nominal_at_least_0_94": cand["nominal"]["top1_accuracy"] >= 0.94,
            "candidate_nominal_loss_at_most_0_035": (
                cand["nominal"]["top1_accuracy"] >= ref["nominal"]["top1_accuracy"] - 0.035),
            "noise_improvement_at_least_0_03": (
                cand["extra_noise_minus_5db"]["top1_accuracy"] >=
                ref["extra_noise_minus_5db"]["top1_accuracy"] + 0.03),
            "cfo_regression_at_most_0_03": (
                cand["cfo_350hz"]["top1_accuracy"] >= ref["cfo_350hz"]["top1_accuracy"] - 0.03),
        },
        "limitations": "Same synthetic generator family, not cross-device or over-the-air performance",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    a = json.loads(args.reference.read_text(encoding="utf-8"))
    b = json.loads(args.candidate.read_text(encoding="utf-8"))
    report = compare(a, b)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    for name, value in report["conditions"].items():
        print(f"{name}: top1 delta={value['delta_top1_percentage_points']:+.2f} pp; "
              f"decision delta={value['delta_operational_percentage_points']:+.2f} pp",
              flush=True)
    for label, ok in report["criteria"].items():
        print(f"{label}: {'PASS' if ok else 'FAIL'}", flush=True)
    if not all(report["criteria"].values()):
        raise SystemExit("Augmented candidate did not meet synthetic promotion criteria; "
                         "retain v2 baseline and examine comparison JSON.")


if __name__ == "__main__":
    main()
