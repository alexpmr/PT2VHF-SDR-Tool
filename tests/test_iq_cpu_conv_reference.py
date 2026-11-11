"""Bounded numerical reference tests; synthetic only, never RF."""
import sys
from pathlib import Path
import pytest

torch = pytest.importorskip("torch")
from torch import nn
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from diagnose_iq_cpu_step import conv1d_scalar_samples, conv1d_float64_reference


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
