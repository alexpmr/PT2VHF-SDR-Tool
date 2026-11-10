"""Synthetic fake-hash tests of CPU probe comparison; no RF data."""
import copy
import pytest
from scripts.compare_iq_cpu_step import compare_reports


def probe(cpu="AMD"):
    return {
        "cpu_model": cpu, "python_version": "3.11", "torch_version": "2.15",
        "numpy_version": "2.4", "policy": {"threads": 1},
        "train_samples": 8400, "unknown_examples_replaced": 100,
        "requested_steps": 2,
        "input_sha256": "x", "validation_input_sha256": "v",
        "initial_parameters_sha256": "p", "epoch0_permutation_sha256": "perm",
        "steps": [{"step": i, "first_conv_scalar_samples": {
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
