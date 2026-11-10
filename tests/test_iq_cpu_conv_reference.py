"""Bounded numerical reference tests; synthetic only, never RF."""
import sys
from pathlib import Path
import pytest

torch = pytest.importorskip("torch")
from torch import nn
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from diagnose_iq_cpu_step import conv1d_scalar_samples


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
