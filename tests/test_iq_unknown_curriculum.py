"""UNKNOWN generator invariants. No Torch/hardware needed."""
import numpy as np
import pytest
from scripts.iq_unknown_curriculum import FAMILIES, unknown_iq


@pytest.mark.parametrize("family",FAMILIES)
def test_unknown_examples_finite_normalized_reproducible(family):
    a=unknown_iq(np.random.default_rng(75),family)
    b=unknown_iq(np.random.default_rng(75),family)
    np.testing.assert_array_equal(a,b)
    assert a.shape==(2,2048)
    assert a.dtype==np.float32
    assert np.isfinite(a).all()
    assert np.sqrt(np.mean(a[0]**2+a[1]**2))==pytest.approx(1,abs=1e-5)
    assert np.linalg.norm(a.mean(axis=1))<1e-4


def test_unknown_generator_random_family_stable():
    np.testing.assert_array_equal(
        unknown_iq(np.random.default_rng(29)),
        unknown_iq(np.random.default_rng(29)))


def test_unknown_generator_rejects_invalid_family():
    with pytest.raises(ValueError):
        unknown_iq(np.random.default_rng(29),"nonexistent")
