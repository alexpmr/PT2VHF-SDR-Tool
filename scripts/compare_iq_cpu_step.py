"""Compare synthetic v4 first-step hashes, explicitly flag same-CPU probes."""
import argparse
import json
import math
from pathlib import Path

GLOBAL = ("input_sha256", "validation_input_sha256",
          "initial_parameters_sha256", "epoch0_permutation_sha256")
STEP = ("indices_sha256", "batch_sha256", "forward_logits_sha256",
        "loss_sha256", "gradients_sha256", "updated_parameters_sha256")
DOUBLE_STEP = ("initial_parameters_sha256", "forward_logits_sha256",
               "loss_sha256", "gradients_sha256", "updated_parameters_sha256")
ADAM_STAGES = ("first_moment", "second_moment", "sqrt_second_moment",
               "denominator", "normalized_update", "manual_updated_parameters")
ADAM_KEYS = ("adam_manual_stage_sha256", "adam_manual_parameter_sha256",
             "adam_native_parameter_sha256")
ENV = ("python_version", "torch_version", "numpy_version", "policy",
       "train_samples", "unknown_examples_replaced", "requested_steps")


def compare_reports(a, b):
    if not a.get("steps") or len(a["steps"]) != len(b.get("steps", [])):
        raise ValueError("Probe step counts differ or are empty")
    matches = {key: a[key] == b[key] for key in GLOBAL}
    first_conv_comparison = None
    second_conv_comparison = None
    second_conv_float64_comparison = None
    float64_first_step_matches = None
    adam_stage_matches = None
    adam_parameter_matches = None
    for i, (left, right) in enumerate(zip(a["steps"], b["steps"])):
        if left["step"] != i or right["step"] != i:
            raise ValueError("Probe step numbering differs")
        left_layers, right_layers = left["layer_forward_sha256"], right["layer_forward_sha256"]
        if list(left_layers) != list(right_layers):
            raise ValueError("Probe layer ordering differs")
        matches.update({f"steps[{i}].layers.{key}": left_layers[key] == right_layers[key]
                        for key in left_layers})
        matches.update({f"steps[{i}].{key}": left[key] == right[key] for key in STEP})
        if i == 0:
            ls, rs = left["first_conv_scalar_samples"], right["first_conv_scalar_samples"]
            count = ls["sample_count"]
            if count < 1 or count != rs["sample_count"]:
                raise ValueError("First Conv1d scalar sample counts differ")
            for label in ("observed", "reference"):
                if len(ls[label]) != count or len(rs[label]) != count:
                    raise ValueError("First Conv1d scalar sample lengths differ")
                if not all(math.isfinite(float(v)) for v in ls[label] + rs[label]):
                    raise ValueError("Non-finite first Conv1d scalar sample")
                matches[f"steps[0].first_conv_scalar_{label}"] = ls[label] == rs[label]
            obs_diff = [abs(x - y) for x, y in zip(ls["observed"], rs["observed"])]
            ref_diff = [abs(x - y) for x, y in zip(ls["reference"], rs["reference"])]
            first_conv_comparison = {
                "sample_count": count,
                "sampled_observed_max_abs_diff": max(obs_diff),
                "sampled_observed_mean_abs_diff": sum(obs_diff) / count,
                "sampled_scalar_reference_max_abs_diff": max(ref_diff),
                "reference_runner_max_abs_error_vs_scalar": ls["max_abs_error"],
                "independent_runner_max_abs_error_vs_scalar": rs["max_abs_error"],
                "scope": "Sparse first-minibatch samples; exact layer hashes still gate",
            }
            sl, sr = left["second_conv_scalar_samples"], right["second_conv_scalar_samples"]
            scount = sl["sample_count"]
            if scount < 1 or scount != sr["sample_count"]:
                raise ValueError("Second Conv1d scalar sample counts differ")
            for label in ("observed", "reference"):
                if len(sl[label]) != scount or len(sr[label]) != scount:
                    raise ValueError("Second Conv1d scalar sample lengths differ")
                if not all(math.isfinite(float(v)) for v in sl[label] + sr[label]):
                    raise ValueError("Non-finite second Conv1d scalar sample")
                matches[f"steps[0].second_conv_scalar_{label}"] = sl[label] == sr[label]
            second_obs_diff = [abs(x - y) for x, y in zip(sl["observed"], sr["observed"])]
            second_ref_diff = [abs(x - y) for x, y in zip(sl["reference"], sr["reference"])]
            second_conv_comparison = {
                "sample_count": scount,
                "sampled_observed_max_abs_diff": max(second_obs_diff),
                "sampled_observed_mean_abs_diff": sum(second_obs_diff) / scount,
                "sampled_scalar_reference_max_abs_diff": max(second_ref_diff),
                "reference_runner_max_abs_error_vs_scalar": sl["max_abs_error"],
                "independent_runner_max_abs_error_vs_scalar": sr["max_abs_error"],
                "scope": "Sparse first-minibatch samples; exact layer hashes still gate",
            }
            lf = left["second_conv_float64_reference"]
            rf = right["second_conv_float64_reference"]
            for report in (lf, rf):
                if not isinstance(report["reference_sha256"], str) or len(report["reference_sha256"]) != 64:
                    raise ValueError("Invalid second Conv1d float64 reference hash")
                if not all(math.isfinite(float(report[key])) and float(report[key]) >= 0
                           for key in ("max_abs_error", "mean_abs_error")):
                    raise ValueError("Invalid second Conv1d float64 error")
            exact64 = lf["reference_sha256"] == rf["reference_sha256"]
            matches["steps[0].second_conv_float64_reference_sha256"] = exact64
            second_conv_float64_comparison = {
                "reference_exact_match": exact64,
                "reference_runner_max_abs_error_vs_native": lf["max_abs_error"],
                "independent_runner_max_abs_error_vs_native": rf["max_abs_error"],
                "scope": "Full second Conv1d first-minibatch float64 diagnostic; no training changes",
            }
            dl, dr = left["float64_first_step"], right["float64_first_step"]
            expected = set(DOUBLE_STEP) | set(ADAM_KEYS)
            if set(dl) != expected or set(dr) != expected:
                raise ValueError("Invalid float64 first-step stage schema")
            for item in (dl, dr):
                for key in DOUBLE_STEP:
                    value = item[key]
                    if not isinstance(value, str) or len(value) != 64 or any(
                            char not in "0123456789abcdef" for char in value):
                        raise ValueError("Invalid float64 first-step SHA-256")
            float64_first_step_matches = {
                key: dl[key] == dr[key] for key in DOUBLE_STEP
            }
            stage_left, stage_right = (dl["adam_manual_stage_sha256"],
                                       dr["adam_manual_stage_sha256"])
            if (not isinstance(stage_left, dict) or not isinstance(stage_right, dict)
                    or set(stage_left) != set(ADAM_STAGES)
                    or set(stage_right) != set(ADAM_STAGES)):
                raise ValueError("Invalid manual Adam stage schema")
            for value in list(stage_left.values()) + list(stage_right.values()):
                if (not isinstance(value, str) or len(value) != 64
                        or any(char not in "0123456789abcdef" for char in value)):
                    raise ValueError("Invalid manual Adam SHA-256")
            adam_stage_matches = {
                key: stage_left[key] == stage_right[key] for key in ADAM_STAGES
            }
            adam_parameter_matches = {}
            for key in ("adam_manual_parameter_sha256", "adam_native_parameter_sha256"):
                left_params, right_params = dl[key], dr[key]
                if (not isinstance(left_params, list) or not isinstance(right_params, list)
                        or not left_params or len(left_params) != len(right_params)):
                    raise ValueError("Invalid Adam parameter count")
                for value in left_params + right_params:
                    if (not isinstance(value, str) or len(value) != 64
                            or any(char not in "0123456789abcdef" for char in value)):
                        raise ValueError("Invalid Adam parameter SHA-256")
                adam_parameter_matches[key] = [
                    x == y for x, y in zip(left_params, right_params)
                ]
    first = next((key for key, ok in matches.items() if not ok), None)
    float64_first = next(
        (key for key, ok in float64_first_step_matches.items() if not ok), None)
    first_adam_stage = next(
        (key for key, ok in adam_stage_matches.items() if not ok), None)
    first_adam_parameters = {
        key: next((i for i, ok in enumerate(flags) if not ok), None)
        for key, flags in adam_parameter_matches.items()
    }
    adam_mismatch = first_adam_stage is not None or any(
        value is not None for value in first_adam_parameters.values())
    env_ok = all(a[key] == b[key] for key in ENV)
    cross_cpu = (a["cpu_model"] != b["cpu_model"]
                 and "unknown" not in (a["cpu_model"], b["cpu_model"]))
    conclusion = ("ENVIRONMENT_MISMATCH" if not env_ok else
                  "NUMERICAL_DIVERGENCE" if first or float64_first or adam_mismatch else
                  "SAME_CPU_ONLY_INCONCLUSIVE" if not cross_cpu else
                  "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY")
    return {
        "scope": "Bounded synthetic v4 first-step diagnostic; no full training or RF",
        "reference_cpu": a["cpu_model"], "independent_cpu": b["cpu_model"],
        "cross_cpu_tested": cross_cpu, "environment_exact_match": env_ok,
        "steps_compared": len(a["steps"]), "first_divergent_stage": first,
        "stage_exact_match": matches, "first_conv_scalar_comparison": first_conv_comparison,
        "second_conv_scalar_comparison": second_conv_comparison,
        "second_conv_float64_comparison": second_conv_float64_comparison,
        "float64_first_step_exact_match": all(float64_first_step_matches.values()),
        "float64_first_step_stage_exact_match": float64_first_step_matches,
        "first_divergent_float64_stage": float64_first,
        "adam_manual_stage_exact_match": adam_stage_matches,
        "first_divergent_adam_stage": first_adam_stage,
        "adam_parameter_exact_match": adam_parameter_matches,
        "first_divergent_adam_parameter": first_adam_parameters,
        "conclusion": conclusion,
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
    if (not report["environment_exact_match"] or report["first_divergent_stage"]
            or report["first_divergent_float64_stage"]
            or report["first_divergent_adam_stage"]
            or any(value is not None for value in
                   report["first_divergent_adam_parameter"].values())):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
