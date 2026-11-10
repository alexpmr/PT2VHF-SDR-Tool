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
        "steps": [{"step": i, "indices_sha256": "idx",
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
