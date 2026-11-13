"""Synthetic-only regression: RF/OOD policy limits must be real numbers, not flags.

A Python bool is an int: max_far=True accepts 100% UNKNOWN false accepts,
while min_coverage=False or min_pipeline_coverage=False disables a gate.
These tests use no RF recordings or model training.
"""
from pathlib import Path

import numpy as np
import pytest

from scripts.iq_session_gate import select, run


ROWS = [
    ("AM", "AM", 0.99, "known-session"),
    ("UNKNOWN", "AM", 0.99, "unknown-session"),
]


@pytest.mark.parametrize("invalid", [
    True, False, "0.1", None, float("nan"), float("inf"), -0.01, 1.01,
])
@pytest.mark.parametrize("field", ["max_far", "min_coverage"])
def test_select_rejects_non_numeric_or_out_of_range_limits(field, invalid):
    kwargs = {"max_far": 0.10, "min_coverage": 0.50}
    kwargs[field] = invalid
    with pytest.raises(ValueError, match="Invalid limits"):
        select(ROWS, **kwargs)


@pytest.mark.parametrize("invalid", [
    True, False, "0.8", None, float("nan"), float("inf"), -0.01, 1.01,
])
def test_run_rejects_invalid_pipeline_limit_before_opening_files(invalid):
    with pytest.raises(ValueError, match="Invalid minimum pipeline coverage"):
        run(Path("nonexistent-cal.json"), Path("nonexistent-hold.json"),
            Path("."), object(), min_pipeline_coverage=invalid)


def test_real_numpy_scalar_limits_remain_supported():
    best, curve = select(ROWS, max_far=np.float64(0.10),
                         min_coverage=np.float64(0.50))
    assert best is None
    assert len(curve) == 5


def test_explicit_numeric_policy_limits_are_not_silently_changed():
    # Explicit numeric 1.0 is permitted by the documented [0, 1] contract;
    # the regression rejects *flags*, not deliberate numerical choices.
    best, _ = select(ROWS, max_far=1.0, min_coverage=0.5)
    assert best is not None
    assert best["unknown_false_accept_rate"] == 1.0
