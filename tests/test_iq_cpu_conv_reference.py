"""Bounded numerical reference tests; synthetic only, never RF."""
import sys
from pathlib import Path
import pytest

torch = pytest.importorskip("torch")
from torch import nn
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from diagnose_iq_cpu_step import (
    conv1d_scalar_samples, conv1d_float64_reference, float64_first_optimizer_step,
    manual_adam_first_step, sqrt_ulp_reference,
)


@pytest.mark.parametrize("padding,stride,dilation,bias", [
    (1, 2, 1, True), (0, 1, 1, False), (2, 3, 2, True),
])
def test_scalar_reference_agrees_with_conv1d(padding, stride, dilation, bias):
    torch.manual_seed(42)
    layer = nn.Conv1d(2, 3, 3, stride=stride, padding=padding,
                      dilation=dilation, bias=bias)
    x = torch.randn(5, 2, 17)
    report = conv1d_scalar_samples(x, layer, layer(x), sample_count=64)
    assert report["sample_count"] == 64
    assert report["max_abs_error"] < 1e-5
    assert report["mean_abs_error"] <= report["max_abs_error"]


def test_scalar_reference_rejects_grouped_convolution():
    layer = nn.Conv1d(2, 2, 3, groups=2)
    x = torch.randn(1, 2, 16)
    with pytest.raises(ValueError, match="ungrouped"):
        conv1d_scalar_samples(x, layer, layer(x))


def test_full_float64_reference_matches_double_native_and_bounds_float32():
    torch.manual_seed(29)
    layer = nn.Conv1d(24, 48, 7, stride=4, padding=3)
    x = torch.randn(4, 24, 128)
    report = conv1d_float64_reference(x, layer, layer(x))
    assert len(report["reference_sha256"]) == 64
    assert 0 <= report["mean_abs_error"] <= report["max_abs_error"] < 1e-5
    double_layer = layer.double()
    double_x = x.double()
    exact = conv1d_float64_reference(double_x, double_layer, double_layer(double_x))
    assert exact["max_abs_error"] == 0.0
    assert exact["reference_sha256"] == report["reference_sha256"]


def test_full_float64_reference_rejects_grouped_convolution():
    layer = nn.Conv1d(2, 2, 3, groups=2)
    x = torch.randn(1, 2, 16)
    with pytest.raises(ValueError, match="ungrouped"):
        conv1d_float64_reference(x, layer, layer(x))


def test_double_first_step_repeats_without_mutating_original_weights():
    torch.manual_seed(20261113)
    from train_iq_synthetic_ci import Net
    model = Net()
    x = torch.randn(2, 2, 2048)
    y = torch.tensor([0, 6])
    original = [weight.detach().clone() for weight in model.parameters()]
    first = float64_first_optimizer_step(model, x, y)
    second = float64_first_optimizer_step(model, x, y)
    assert first == second
    assert set(first) == {
        "initial_parameters_sha256", "forward_logits_sha256", "loss_sha256",
        "gradients_sha256", "updated_parameters_sha256",
        "adam_manual_stage_sha256", "adam_sqrt_oracle", "adam_manual_parameter_sha256",
        "adam_native_parameter_sha256",
    }
    assert first["initial_parameters_sha256"] != first["updated_parameters_sha256"]
    assert all(torch.equal(before, after) for before, after in zip(original, model.parameters()))



def test_manual_adam_diagnostic_is_read_only_and_repeatable():
    p = nn.Parameter(torch.tensor([1.0, -2.0], dtype=torch.float64))
    p.grad = torch.tensor([0.1, -0.2], dtype=torch.float64)
    before = p.detach().clone()
    first = manual_adam_first_step([p])
    assert first == manual_adam_first_step([p])
    assert torch.equal(p, before)
    assert len(first["stage_sha256"]) == 6
    assert len(first["parameter_sha256"]) == 1
    assert all(len(value) == 64 for value in first["stage_sha256"].values())
    p.grad = None
    with pytest.raises(ValueError, match="requires gradients"):
        manual_adam_first_step([p])



def test_sqrt_decimal_oracle_detects_single_ulp_drift_without_changing_inputs():
    moments = torch.tensor([0.0, 1.0, 2.0, 3.0, 1e-300], dtype=torch.float64)
    native = moments.sqrt()
    before = moments.clone()
    reference = sqrt_ulp_reference([moments], [native])
    assert reference["sample_count"] == 4
    assert reference["max_ulp_error"] <= 1
    assert reference["oracle_sha256"] == reference["native_sha256"]
    changed = torch.nextafter(native, torch.full_like(native, float("inf")))
    drift = sqrt_ulp_reference([moments], [changed])
    assert drift["oracle_sha256"] == reference["oracle_sha256"]
    assert drift["native_sha256"] != reference["native_sha256"]
    assert drift["mismatch_count"] == 4
    assert drift["first_mismatch"]["tensor_index"] == 0
    assert drift["first_mismatch"]["ulp_error"] == 1
    assert torch.equal(moments, before)


def test_sqrt_decimal_oracle_rejects_invalid_inputs():
    x = torch.tensor([1.0], dtype=torch.float64)
    with pytest.raises(ValueError, match="matched float64"):
        sqrt_ulp_reference([x], [x.float()])
    with pytest.raises(ValueError, match="finite nonnegative"):
        sqrt_ulp_reference([torch.tensor([-1.0], dtype=torch.float64)], [x])
    with pytest.raises(ValueError, match="no positive"):
        sqrt_ulp_reference([torch.zeros_like(x)], [torch.zeros_like(x)])
