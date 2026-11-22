"""Synthetic fake-hash tests of CPU probe comparison; no RF data."""
import copy
import pytest
from scripts.compare_iq_cpu_step import compare_reports, DOUBLE_STEP, ADAM_STAGES


def probe(cpu="AMD"):
    return {
        "cpu_model": cpu, "python_version": "3.11", "torch_version": "2.15",
        "numpy_version": "2.4", "cpu_capability": "DEFAULT", "policy": {
            "portable_cpu": True, "threads": 1, "mkldnn_enabled": False,
            "deterministic_algorithms": True, "aten_cpu_capability": "default",
            "mkl_cbwr": "COMPATIBLE"},
        "train_samples": 8400, "unknown_examples_replaced": 100,
        "requested_steps": 2,
        "input_sha256": "1" * 64, "validation_input_sha256": "2" * 64,
        "initial_parameters_sha256": "3" * 64, "epoch0_permutation_sha256": "4" * 64,
        "steps": [{"step": i, "second_conv_scalar_samples": {
                       "sample_count": 2, "observed": [3.0, 4.0],
                       "reference": [3.0, 4.0],
                       "max_abs_error": 0.0, "mean_abs_error": 0.0},
                   "float64_first_step": {
                       **{key: "a" * 64 for key in DOUBLE_STEP},
                       "adam_sqrt_oracle": {
                           "sample_count": 32, "native_sha256": "a" * 64,
                           "oracle_sha256": "a" * 64, "mismatch_count": 0,
                           "max_ulp_error": 0, "first_mismatch": None,
                       },
                       "adam_manual_stage_sha256": {
                           key: "a" * 64 for key in ADAM_STAGES},
                       "adam_manual_parameter_sha256": ["a" * 64, "a" * 64],
                       "adam_native_parameter_sha256": ["a" * 64, "a" * 64],
                   },
                   "second_conv_float64_reference": {
                       "reference_sha256": "a" * 64,
                       "max_abs_error": 0.00001,
                       "mean_abs_error": 0.000001},
                   "first_conv_scalar_samples": {
                       "sample_count": 2, "observed": [1.0, 2.0],
                       "reference": [1.0, 2.0],
                       "max_abs_error": 0.0, "mean_abs_error": 0.0},
                   "layer_forward_sha256": {
                       "00_Conv1d": "c" * 64, "01_ReLU": "d" * 64},
                   "indices_sha256": "5" * 64,
                   "batch_sha256": "6" * 64, "forward_logits_sha256": "7" * 64,
                   "loss_sha256": "8" * 64, "gradients_sha256": "9" * 64,
                   "updated_parameters_sha256": "a" * 64} for i in range(2)],
    }


def test_same_cpu_is_inconclusive():
    a = probe()
    result = compare_reports(a, copy.deepcopy(a))
    assert result["conclusion"] == "SAME_CPU_ONLY_INCONCLUSIVE"
    assert result["cross_cpu_tested"] is False


def test_first_divergence_is_reported():
    a, b = probe(), probe("Intel")
    b["steps"][1]["gradients_sha256"] = "b" * 64
    b["steps"][1]["updated_parameters_sha256"] = "e" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[1].gradients_sha256"
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_environment_mismatch_is_not_a_valid_replay():
    a, b = probe(), probe("Intel")
    b["torch_version"] = "2.16"
    assert compare_reports(a, b)["conclusion"] == "ENVIRONMENT_MISMATCH"


def test_invalid_steps_fail_closed():
    a, b = probe(), probe()
    b["steps"] = []
    with pytest.raises(ValueError, match="step counts"):
        compare_reports(a, b)
    b = probe()
    b["steps"][1]["step"] = 4
    with pytest.raises(ValueError, match="numbering"):
        compare_reports(a, b)

def test_first_divergent_layer_precedes_logits_and_gradients():
    a, b = probe(), probe("Intel")
    b["steps"][0]["layer_forward_sha256"]["00_Conv1d"] = "b" * 64
    b["steps"][0]["forward_logits_sha256"] = "b" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].layers.00_Conv1d"
    assert result["cross_cpu_tested"] is True


def test_layer_order_mismatch_fails_closed():
    a, b = probe(), probe("Intel")
    b["steps"][0]["layer_forward_sha256"] = {"00_Conv1d": "c" * 64}
    with pytest.raises(ValueError, match="layer ordering"):
        compare_reports(a, b)


def test_scalar_sample_comparison_quantifies_float_differences():
    a, b = probe(), probe("Intel")
    sample = b["steps"][0]["first_conv_scalar_samples"]
    sample["observed"][1] += 0.00001
    sample["max_abs_error"] = abs(sample["observed"][1] - sample["reference"][1])
    sample["mean_abs_error"] = sample["max_abs_error"] / sample["sample_count"]
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].first_conv_scalar_observed"
    assert abs(result["first_conv_scalar_comparison"]["sampled_observed_max_abs_diff"] - 0.00001) < 1e-10
    assert result["first_conv_scalar_comparison"]["sampled_scalar_reference_max_abs_diff"] == 0.0


def test_malformed_or_nonfinite_scalar_samples_fail_closed():
    a, b = probe(), probe("Intel")
    b["steps"][0]["first_conv_scalar_samples"]["observed"] = [1.0]
    with pytest.raises(ValueError, match="sample lengths"):
        compare_reports(a, b)
    b = probe("Intel")
    b["steps"][0]["first_conv_scalar_samples"]["reference"][0] = float("nan")
    with pytest.raises(ValueError, match="Non-finite"):
        compare_reports(a, b)


def test_second_conv_scalar_comparison_reports_drift():
    a, b = probe(), probe("Intel")
    a["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "a" * 64
    b["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "b" * 64
    sample = b["steps"][0]["second_conv_scalar_samples"]
    sample["observed"][0] += 0.00002
    sample["max_abs_error"] = abs(sample["observed"][0] - sample["reference"][0])
    sample["mean_abs_error"] = sample["max_abs_error"] / sample["sample_count"]
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].layers.02_Conv1d"
    assert abs(result["second_conv_scalar_comparison"]["sampled_observed_max_abs_diff"] - 0.00002) < 1e-10
    assert result["first_conv_scalar_comparison"]["sampled_observed_max_abs_diff"] == 0.0


def test_float64_reference_exact_match_is_independent_of_float32_divergence():
    a, b = probe(), probe("Intel")
    a["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "a" * 64
    b["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "b" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].layers.02_Conv1d"
    assert result["second_conv_float64_comparison"]["reference_exact_match"] is True
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_float64_reference_mismatch_and_nonfinite_error_fail_closed():
    a, b = probe(), probe("Intel")
    b["steps"][0]["second_conv_float64_reference"]["reference_sha256"] = "b" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].second_conv_float64_reference_sha256"
    assert result["second_conv_float64_comparison"]["reference_exact_match"] is False
    b["steps"][0]["second_conv_float64_reference"]["max_abs_error"] = float("nan")
    with pytest.raises(ValueError, match="float64 error"):
        compare_reports(a, b)


def test_float64_first_step_matches_despite_float32_layer_divergence():
    a, b = probe(), probe("Intel")
    b["steps"][0]["layer_forward_sha256"]["01_ReLU"] = "b" * 64
    result = compare_reports(a, b)
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"
    assert result["float64_first_step_exact_match"] is True
    assert result["first_divergent_float64_stage"] is None


def test_float64_first_step_divergence_is_separately_reported():
    a, b = probe(), probe("Intel")
    b["steps"][0]["float64_first_step"]["gradients_sha256"] = "b" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] is None
    assert result["first_divergent_float64_stage"] == "gradients_sha256"
    assert result["float64_first_step_exact_match"] is False
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_float64_first_step_missing_or_invalid_hash_fails_closed():
    a, b = probe(), probe("Intel")
    del b["steps"][0]["float64_first_step"]["loss_sha256"]
    with pytest.raises(ValueError, match="stage schema"):
        compare_reports(a, b)
    b = probe("Intel")
    b["steps"][0]["float64_first_step"]["loss_sha256"] = "not-a-sha256"
    with pytest.raises(ValueError, match="SHA-256"):
        compare_reports(a, b)



def test_manual_adam_stage_divergence_is_fail_closed():
    a, b = probe(), probe("Intel")
    b["steps"][0]["float64_first_step"]["adam_manual_stage_sha256"]["denominator"] = "b" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] is None
    assert result["first_divergent_float64_stage"] is None
    assert result["first_divergent_adam_stage"] == "denominator"
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_adam_per_parameter_divergence_identifies_tensor_index():
    a, b = probe(), probe("Intel")
    b["steps"][0]["float64_first_step"]["adam_native_parameter_sha256"][1] = "b" * 64
    result = compare_reports(a, b)
    assert result["first_divergent_adam_parameter"]["adam_native_parameter_sha256"] == 1
    assert result["first_divergent_adam_parameter"]["adam_manual_parameter_sha256"] is None
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_malformed_adam_stage_and_parameter_hashes_fail_closed():
    a, b = probe(), probe("Intel")
    del b["steps"][0]["float64_first_step"]["adam_manual_stage_sha256"]["denominator"]
    with pytest.raises(ValueError, match="manual Adam stage schema"):
        compare_reports(a, b)
    b = probe("Intel")
    b["steps"][0]["float64_first_step"]["adam_native_parameter_sha256"][0] = "bad"
    with pytest.raises(ValueError, match="Adam parameter SHA-256"):
        compare_reports(a, b)



def test_sqrt_oracle_comparison_flags_native_drift_and_preserves_oracle():
    a, b = probe(), probe("Intel")
    b["steps"][0]["float64_first_step"]["adam_sqrt_oracle"]["native_sha256"] = "b" * 64
    b["steps"][0]["float64_first_step"]["adam_sqrt_oracle"]["mismatch_count"] = 1
    result = compare_reports(a, b)
    comparison = result["adam_sqrt_oracle_comparison"]
    assert comparison["oracle_exact_match"] is True
    assert comparison["native_exact_match"] is False
    assert comparison["independent_mismatch_count"] == 1
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_sqrt_oracle_malformed_samples_fail_closed():
    a, b = probe(), probe("Intel")
    b["steps"][0]["float64_first_step"]["adam_sqrt_oracle"]["sample_count"] = 0
    with pytest.raises(ValueError, match="oracle counts"):
        compare_reports(a, b)
    b = probe("Intel")
    b["steps"][0]["float64_first_step"]["adam_sqrt_oracle"]["oracle_sha256"] = "invalid"
    with pytest.raises(ValueError, match="oracle SHA-256"):
        compare_reports(a, b)


@pytest.mark.parametrize("digest_key", ["native_sha256", "oracle_sha256"])
def test_cli_fails_closed_on_isolated_sqrt_oracle_hash_drift(tmp_path, digest_key):
    """An isolated sampled sqrt hash mismatch must fail the CLI, not just JSON."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    reference, independent = probe(), probe("Intel")
    independent["steps"][0]["float64_first_step"]["adam_sqrt_oracle"][digest_key] = "b" * 64
    left = tmp_path / "reference.json"
    right = tmp_path / "independent.json"
    output = tmp_path / "comparison.json"
    left.write_text(json.dumps(reference), encoding="utf-8")
    right.write_text(json.dumps(independent), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "compare_iq_cpu_step.py"
    result = subprocess.run(
        [sys.executable, str(script), "--reference", str(left),
         "--independent", str(right), "--out", str(output)],
        capture_output=True, text=True, timeout=15,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["conclusion"] == "NUMERICAL_DIVERGENCE"
    assert report["first_divergent_stage"] is None
    assert report["first_divergent_float64_stage"] is None
    assert report["first_divergent_adam_stage"] is None
    assert all(value is None for value in report["first_divergent_adam_parameter"].values())
    assert result.returncode == 2


@pytest.mark.parametrize(
    "independent_cpu,expected_conclusion,expected_exit",
    [("AMD", "SAME_CPU_ONLY_INCONCLUSIVE", 3),
     ("Intel", "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY", 0)],
)
def test_cli_distinguishes_same_cpu_inconclusive_from_cross_cpu_match(
        tmp_path, independent_cpu, expected_conclusion, expected_exit):
    """Matching synthetic hashes on one CPU model must not yield a green gate."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    reference = tmp_path / "reference.json"
    independent = tmp_path / "independent.json"
    output = tmp_path / "comparison.json"
    reference.write_text(json.dumps(probe()), encoding="utf-8")
    independent.write_text(json.dumps(probe(independent_cpu)), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "compare_iq_cpu_step.py"
    result = subprocess.run(
        [sys.executable, str(script), "--reference", str(reference),
         "--independent", str(independent), "--out", str(output)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == expected_exit
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["conclusion"] == expected_conclusion
    assert report["cross_cpu_tested"] is (independent_cpu != "AMD")
    assert report["first_divergent_stage"] is None


def test_cpu_vendor_classification_is_conservative():
    from scripts.compare_iq_cpu_step import cpu_vendor
    assert cpu_vendor("AMD EPYC 7763 64-Core Processor") == "amd"
    assert cpu_vendor("Intel(R) Xeon(R) Platinum 8370C CPU") == "intel"
    assert cpu_vendor("Intel(R) Core(TM) i7") == "intel"
    assert cpu_vendor("AMD Ryzen 9") == "amd"
    assert cpu_vendor("unknown") == "unknown"
    assert cpu_vendor("Virtual CPU") == "unknown"
    assert cpu_vendor("AMD Intel hybrid") == "unknown"


def test_distinct_models_same_vendor_cannot_pass_amd_intel_gate():
    a, b = probe("Intel Xeon Platinum"), probe("Intel Core i7")
    report = compare_reports(a, b)
    assert report["cross_cpu_tested"] is True
    assert report["cross_vendor_tested"] is False
    assert report["conclusion"] == "SAME_VENDOR_ONLY_INCONCLUSIVE"


def test_unknown_cpu_vendor_cannot_pass_amd_intel_gate():
    a, b = probe("AMD EPYC"), probe("Virtual CPU 42")
    report = compare_reports(a, b)
    assert report["cross_vendor_tested"] is False
    assert report["conclusion"] == "CPU_VENDOR_UNKNOWN_INCONCLUSIVE"


@pytest.mark.parametrize("capability", ["AVX2", "AVX512", "default"])
def test_identically_nonportable_effective_cpu_capability_fails_closed(capability):
    """Matching non-default kernel dispatch cannot certify portable AMD/Intel QA."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["cpu_capability"] = b["cpu_capability"] = capability
    with pytest.raises(ValueError, match="effective capability"):
        compare_reports(a, b)


def test_cpu_capability_mismatch_is_rejected_before_comparison():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["cpu_capability"] = "AVX2"
    with pytest.raises(ValueError, match="effective capability"):
        compare_reports(a, b)


def test_effective_default_cpu_capability_allows_bounded_comparison():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    assert compare_reports(a, b)["conclusion"] == "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY"


def test_amd_intel_probe_match_still_not_full_replay():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    report = compare_reports(a, b)
    assert report["cross_vendor_tested"] is True
    assert report["conclusion"] == "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY"


def test_cli_same_vendor_probe_is_inconclusive(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    left, right, out = (tmp_path / name for name in ("a.json", "b.json", "out.json"))
    left.write_text(json.dumps(probe("Intel Xeon")), encoding="utf-8")
    right.write_text(json.dumps(probe("Intel Core i7")), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "compare_iq_cpu_step.py"
    proc = subprocess.run([sys.executable, str(script), "--reference", str(left),
                           "--independent", str(right), "--out", str(out)],
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 3
    assert json.loads(out.read_text(encoding="utf-8"))["conclusion"] == "SAME_VENDOR_ONLY_INCONCLUSIVE"


@pytest.mark.parametrize("requested", [0, -1, 3, True, "2", None, 67])
def test_requested_steps_must_match_complete_probe(requested):
    """Matching truncated JSON reports cannot certify four requested steps."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["requested_steps"] = requested
    b["requested_steps"] = requested
    with pytest.raises(ValueError, match="requested_steps"):
        compare_reports(a, b)


def test_equal_length_truncated_probes_are_rejected():
    """Both hosts losing the same final step must still fail closed."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["steps"] = a["steps"][:1]
    b["steps"] = b["steps"][:1]
    with pytest.raises(ValueError, match="requested_steps"):
        compare_reports(a, b)


def test_valid_one_step_probe_is_limited_not_full_replay():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["requested_steps"] = b["requested_steps"] = 1
    a["steps"] = a["steps"][:1]
    b["steps"] = b["steps"][:1]
    result = compare_reports(a, b)
    assert result["steps_compared"] == 1
    assert result["conclusion"] == "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY"


@pytest.mark.parametrize("layer", ["first_conv_scalar_samples", "second_conv_scalar_samples"])
@pytest.mark.parametrize("metric,bad_value", [
    ("max_abs_error", float("nan")),
    ("max_abs_error", float("inf")),
    ("max_abs_error", -1.0),
    ("mean_abs_error", -0.01),
    ("mean_abs_error", "0.0"),
    ("mean_abs_error", True),
])
def test_cpu_probe_rejects_invalid_scalar_error_metadata(layer, metric, bad_value):
    """Malformed scalar diagnostics must never support a green CPU comparison."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0][layer][metric] = bad_value
    with pytest.raises(ValueError, match="scalar"):
        compare_reports(a, b)


@pytest.mark.parametrize("layer", ["first_conv_scalar_samples", "second_conv_scalar_samples"])
def test_cpu_probe_rejects_scalar_mean_exceeding_max_and_boolean_count(layer):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0][layer]["mean_abs_error"] = 0.1
    with pytest.raises(ValueError, match="mean exceeds maximum"):
        compare_reports(a, b)
    b = probe("Intel Xeon")
    b["steps"][0][layer]["sample_count"] = True
    with pytest.raises(ValueError, match="sample count"):
        compare_reports(a, b)


@pytest.mark.parametrize("layer", ["first_conv_scalar_samples", "second_conv_scalar_samples"])
def test_matching_inconsistent_scalar_reports_cannot_pass_cross_cpu(layer):
    """Two identically corrupted reports must not certify AMD x Intel agreement."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    for report in (a, b):
        report["steps"][0][layer]["observed"][0] += 0.25
        # The zero-valued summaries are now inconsistent with their samples.
    with pytest.raises(ValueError, match="Inconsistent .* scalar error summary"):
        compare_reports(a, b)


@pytest.mark.parametrize("layer", ["first_conv_scalar_samples", "second_conv_scalar_samples"])
@pytest.mark.parametrize("bad_value", [True, "1.0", None])
def test_cpu_probe_rejects_non_numeric_scalar_samples(layer, bad_value):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0][layer]["observed"][0] = bad_value
    with pytest.raises(ValueError, match="scalar sample"):
        compare_reports(a, b)


@pytest.mark.parametrize("layer", ["first_conv_scalar_samples", "second_conv_scalar_samples"])
def test_cpu_probe_accepts_consistent_nonzero_scalar_error(layer):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    sample = b["steps"][0][layer]
    sample["observed"][0] += 0.125
    sample["max_abs_error"] = 0.125
    sample["mean_abs_error"] = 0.0625
    result = compare_reports(a, b)
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


@pytest.mark.parametrize("field,bad", [
    ("max_abs_error", True),
    ("max_abs_error", "0.0001"),
    ("max_abs_error", None),
    ("max_abs_error", float("inf")),
    ("max_abs_error", -0.1),
    ("mean_abs_error", False),
    ("mean_abs_error", "0"),
    ("mean_abs_error", float("nan")),
])
def test_cpu_float64_reference_rejects_invalid_numeric_metadata(field, bad):
    """Do not coerce invalid evidence into a green AMD/Intel comparison."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0]["second_conv_float64_reference"][field] = bad
    with pytest.raises(ValueError, match="float64 error"):
        compare_reports(a, b)


@pytest.mark.parametrize("digest", ["g" * 64, "A" * 64, "a" * 63, None])
def test_cpu_float64_reference_rejects_non_sha256_digest(digest):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0]["second_conv_float64_reference"]["reference_sha256"] = digest
    with pytest.raises(ValueError, match="float64 reference hash"):
        compare_reports(a, b)


def test_cpu_float64_reference_rejects_mean_above_maximum():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0]["second_conv_float64_reference"]["mean_abs_error"] = 0.1
    with pytest.raises(ValueError, match="float64 mean exceeds maximum"):
        compare_reports(a, b)


def test_cpu_float64_reference_rejects_unexpected_schema_field():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0]["second_conv_float64_reference"]["unverified"] = True
    with pytest.raises(ValueError, match="float64 reference schema"):
        compare_reports(a, b)


def test_cpu_float64_reference_accepts_valid_nonzero_error_metadata():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0]["second_conv_float64_reference"]["max_abs_error"] = 0.125
    b["steps"][0]["second_conv_float64_reference"]["mean_abs_error"] = 0.0625
    result = compare_reports(a, b)
    assert result["conclusion"] == "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY"


@pytest.mark.parametrize("field,value,match_field", [
    ("mismatch_count", 1, "mismatch_count_exact_match"),
    ("max_ulp_error", 1, "max_ulp_error_exact_match"),
    ("first_mismatch", {
        "tensor_index": 0, "flat_index": 0,
        "native_hex": "0x1.0000000000001p+0",
        "oracle_hex": "0x1.0000000000000p+0",
        "ulp_error": 1,
    }, "first_mismatch_exact_match"),
])
def test_sqrt_oracle_metadata_drift_blocks_false_cross_vendor_pass(
        field, value, match_field):
    """Matching digests cannot override contradictory sampled-sqrt metadata.

    These are deliberately malformed synthetic reports, not CPU measurements.
    """
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    b["steps"][0]["float64_first_step"]["adam_sqrt_oracle"][field] = value
    result = compare_reports(a, b)
    assert result["cross_vendor_tested"] is True
    assert result["first_divergent_stage"] is None
    assert result["adam_sqrt_oracle_comparison"]["oracle_exact_match"] is True
    assert result["adam_sqrt_oracle_comparison"]["native_exact_match"] is True
    assert result["adam_sqrt_oracle_comparison"][match_field] is False
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


@pytest.mark.parametrize("corruption", [
    "equal_hashes_but_mismatch",
    "different_hashes_but_zero_mismatches",
    "missing_first_mismatch",
    "incorrect_ulp_witness",
    "invalid_hex_witness",
])
def test_identically_corrupt_adam_sqrt_reports_never_pass_cross_vendor(corruption):
    """Two matching but impossible diagnostic reports are not CPU evidence."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    for report in (a, b):
        witness = report["steps"][0]["float64_first_step"]["adam_sqrt_oracle"]
        if corruption == "different_hashes_but_zero_mismatches":
            witness["native_sha256"] = "b" * 64
        else:
            witness["mismatch_count"] = 1
            witness["max_ulp_error"] = 1
            if corruption != "equal_hashes_but_mismatch":
                witness["native_sha256"] = "b" * 64
            if corruption in ("incorrect_ulp_witness", "invalid_hex_witness"):
                witness["first_mismatch"] = {
                    "tensor_index": 0, "flat_index": 0,
                    "native_hex": "0x1.0000000000001p+0",
                    "oracle_hex": "0x1.0000000000000p+0",
                    "ulp_error": 2 if corruption == "incorrect_ulp_witness" else 1,
                }
                if corruption == "invalid_hex_witness":
                    witness["first_mismatch"]["native_hex"] = "not-a-float"
    result = compare_reports(a, b)
    evidence = result["adam_sqrt_oracle_comparison"]
    assert evidence["reference_internal_consistency"] is False
    assert evidence["independent_internal_consistency"] is False
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_consistent_adam_sqrt_mismatch_witness_is_not_a_false_metadata_error():
    """A genuine one-ULP native/oracle difference can be internally coherent.

    The reports are synthetic fixtures; agreement still does not certify a
    complete v4 training replay or any RF performance.
    """
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    for report in (a, b):
        witness = report["steps"][0]["float64_first_step"]["adam_sqrt_oracle"]
        witness.update({
            "native_sha256": "b" * 64,
            "mismatch_count": 1,
            "max_ulp_error": 1,
            "first_mismatch": {
                "tensor_index": 0, "flat_index": 0,
                "native_hex": "0x1.0000000000001p+0",
                "oracle_hex": "0x1.0000000000000p+0",
                "ulp_error": 1,
            },
        })
    result = compare_reports(a, b)
    evidence = result["adam_sqrt_oracle_comparison"]
    assert evidence["reference_internal_consistency"] is True
    assert evidence["independent_internal_consistency"] is True
    assert result["conclusion"] == "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY"


@pytest.mark.parametrize("field", [
    "input_sha256", "validation_input_sha256",
    "initial_parameters_sha256", "epoch0_permutation_sha256",
])
@pytest.mark.parametrize("bad", [None, True, "x" * 64, "A" * 64, "0" * 63])
def test_matching_malformed_global_hashes_cannot_pass_cpu_gate(field, bad):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a[field] = b[field] = bad
    with pytest.raises(ValueError, match="Invalid SHA-256"):
        compare_reports(a, b)


@pytest.mark.parametrize("field", [
    "indices_sha256", "batch_sha256", "forward_logits_sha256",
    "loss_sha256", "gradients_sha256", "updated_parameters_sha256",
])
def test_matching_malformed_step_hashes_cannot_pass_cpu_gate(field):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["steps"][1][field] = b["steps"][1][field] = "not-a-digest"
    with pytest.raises(ValueError, match="Invalid SHA-256"):
        compare_reports(a, b)


@pytest.mark.parametrize("bad", [None, True, "G" * 64, "f" * 65])
def test_matching_malformed_layer_hashes_cannot_pass_cpu_gate(bad):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["steps"][0]["layer_forward_sha256"]["00_Conv1d"] = bad
    b["steps"][0]["layer_forward_sha256"]["00_Conv1d"] = bad
    with pytest.raises(ValueError, match="Invalid SHA-256"):
        compare_reports(a, b)


@pytest.mark.parametrize("field,bad", [
    ("cpu_model", None), ("cpu_model", ""),
    ("cpu_capability", False), ("cpu_capability", ""),
    ("python_version", None), ("torch_version", 215),
    ("numpy_version", ""), ("train_samples", True),
    ("train_samples", "8400"), ("train_samples", 8399),
    ("unknown_examples_replaced", False),
    ("unknown_examples_replaced", -1),
    ("unknown_examples_replaced", 8401),
    ("unknown_examples_replaced", "100"),
])
def test_identically_invalid_cpu_environment_never_passes(field, bad):
    """Equal corrupted metadata on both hosts must not produce a green gate."""
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a[field] = b[field] = bad
    with pytest.raises(ValueError, match="CPU probe"):
        compare_reports(a, b)


@pytest.mark.parametrize("field,bad", [
    ("portable_cpu", False),
    ("portable_cpu", 1),
    ("threads", True),
    ("threads", 2),
    ("mkldnn_enabled", True),
    ("deterministic_algorithms", False),
    ("aten_cpu_capability", "avx2"),
    ("mkl_cbwr", ""),
])
def test_identically_invalid_portable_cpu_policy_never_passes(field, bad):
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    a["policy"][field] = b["policy"][field] = bad
    with pytest.raises(ValueError, match="CPU probe portable policy"):
        compare_reports(a, b)


def test_missing_or_extra_portable_policy_fields_fail_closed():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    for report in (a, b):
        del report["policy"]["mkl_cbwr"]
    with pytest.raises(ValueError, match="portable policy schema"):
        compare_reports(a, b)
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    for report in (a, b):
        report["policy"]["unverified"] = True
    with pytest.raises(ValueError, match="portable policy schema"):
        compare_reports(a, b)


def test_valid_portable_probe_environment_keeps_bounded_cross_vendor_result():
    a, b = probe("AMD EPYC"), probe("Intel Xeon")
    assert compare_reports(a, b)["conclusion"] == "FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY"
