"""Synthetic fake-hash tests of CPU probe comparison; no RF data."""
import copy
import pytest
from scripts.compare_iq_cpu_step import compare_reports, DOUBLE_STEP, ADAM_STAGES


def probe(cpu="AMD"):
    return {
        "cpu_model": cpu, "python_version": "3.11", "torch_version": "2.15",
        "numpy_version": "2.4", "policy": {"threads": 1},
        "train_samples": 8400, "unknown_examples_replaced": 100,
        "requested_steps": 2,
        "input_sha256": "x", "validation_input_sha256": "v",
        "initial_parameters_sha256": "p", "epoch0_permutation_sha256": "perm",
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
                       "00_Conv1d": "conv", "01_ReLU": "relu"},
                   "indices_sha256": "idx",
                   "batch_sha256": "batch", "forward_logits_sha256": "logits",
                   "loss_sha256": "loss", "gradients_sha256": "grad",
                   "updated_parameters_sha256": "weights"} for i in range(2)],
    }


def test_same_cpu_is_inconclusive():
    a = probe()
    result = compare_reports(a, copy.deepcopy(a))
    assert result["conclusion"] == "SAME_CPU_ONLY_INCONCLUSIVE"
    assert result["cross_cpu_tested"] is False


def test_first_divergence_is_reported():
    a, b = probe(), probe("Intel")
    b["steps"][1]["gradients_sha256"] = "changed"
    b["steps"][1]["updated_parameters_sha256"] = "also changed"
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[1].gradients_sha256"
    assert result["conclusion"] == "NUMERICAL_DIVERGENCE"


def test_environment_mismatch_is_not_a_valid_replay():
    a, b = probe(), probe("Intel")
    b["policy"]["threads"] = 2
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
    b["steps"][0]["layer_forward_sha256"]["00_Conv1d"] = "changed"
    b["steps"][0]["forward_logits_sha256"] = "changed"
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].layers.00_Conv1d"
    assert result["cross_cpu_tested"] is True


def test_layer_order_mismatch_fails_closed():
    a, b = probe(), probe("Intel")
    b["steps"][0]["layer_forward_sha256"] = {"00_Conv1d": "conv"}
    with pytest.raises(ValueError, match="layer ordering"):
        compare_reports(a, b)


def test_scalar_sample_comparison_quantifies_float_differences():
    a, b = probe(), probe("Intel")
    b["steps"][0]["first_conv_scalar_samples"]["observed"][1] += 0.00001
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
    a["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "original"
    b["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "different"
    b["steps"][0]["second_conv_scalar_samples"]["observed"][0] += 0.00002
    result = compare_reports(a, b)
    assert result["first_divergent_stage"] == "steps[0].layers.02_Conv1d"
    assert abs(result["second_conv_scalar_comparison"]["sampled_observed_max_abs_diff"] - 0.00002) < 1e-10
    assert result["first_conv_scalar_comparison"]["sampled_observed_max_abs_diff"] == 0.0


def test_float64_reference_exact_match_is_independent_of_float32_divergence():
    a, b = probe(), probe("Intel")
    a["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "original"
    b["steps"][0]["layer_forward_sha256"]["02_Conv1d"] = "changed"
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
    b["steps"][0]["layer_forward_sha256"]["01_ReLU"] = "different"
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
