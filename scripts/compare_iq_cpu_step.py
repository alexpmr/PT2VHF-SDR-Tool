"""Compare synthetic v4 first-step hashes, explicitly flag same-CPU probes."""
import argparse
import json
from pathlib import Path

GLOBAL = ("input_sha256", "validation_input_sha256",
          "initial_parameters_sha256", "epoch0_permutation_sha256")
STEP = ("indices_sha256", "batch_sha256", "forward_logits_sha256",
        "loss_sha256", "gradients_sha256", "updated_parameters_sha256")
ENV = ("python_version", "torch_version", "numpy_version", "policy",
       "train_samples", "unknown_examples_replaced", "requested_steps")


def compare_reports(a, b):
    if not a.get("steps") or len(a["steps"]) != len(b.get("steps", [])):
        raise ValueError("Probe step counts differ or are empty")
    matches = {key: a[key] == b[key] for key in GLOBAL}
    for i, (left, right) in enumerate(zip(a["steps"], b["steps"])):
        if left["step"] != i or right["step"] != i:
            raise ValueError("Probe step numbering differs")
        matches.update({f"steps[{i}].{key}": left[key] == right[key] for key in STEP})
    first = next((key for key, ok in matches.items() if not ok), None)
    env_ok = all(a[key] == b[key] for key in ENV)
    cross_cpu = (a["cpu_model"] != b["cpu_model"]
                 and "unknown" not in (a["cpu_model"], b["cpu_model"]))
    conclusion = ("ENVIRONMENT_MISMATCH" if not env_ok else
                  "NUMERICAL_DIVERGENCE" if first else
                  "SAME_CPU_ONLY_INCONCLUSIVE" if not cross_cpu else
                  "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY")
    return {
        "scope": "Bounded synthetic v4 first-step diagnostic; no full training or RF",
        "reference_cpu": a["cpu_model"], "independent_cpu": b["cpu_model"],
        "cross_cpu_tested": cross_cpu, "environment_exact_match": env_ok,
        "steps_compared": len(a["steps"]), "first_divergent_stage": first,
        "stage_exact_match": matches, "conclusion": conclusion,
        "limitations": "Matching early steps cannot prove 22-epoch reproducibility",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--independent", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    report = compare_reports(json.loads(args.reference.read_text()),
                             json.loads(args.independent.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
    if not report["environment_exact_match"] or report["first_divergent_stage"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
