"""Deterministic tests for the new, independent IQ test generator."""
import numpy as np
import pytest

from scripts.iq_out_of_family import NEGATIVES, SUPPORTED, N, negative, sample


@pytest.mark.parametrize("mode", SUPPORTED)
def test_independent_ood_generator_valid_and_repeatable(mode):
    a = sample(mode, np.random.default_rng(114), 9)
    b = sample(mode, np.random.default_rng(114), 9)
    np.testing.assert_array_equal(a, b)
    assert a.shape == (N,)
    assert a.dtype == np.complex64
    assert np.isfinite(a).all()
    assert np.sqrt(np.mean(np.abs(a) ** 2)) == pytest.approx(1, abs=1e-6)


@pytest.mark.parametrize("kind", NEGATIVES)
def test_unlabelled_negative_signals_are_finite(kind):
    x = negative(kind, np.random.default_rng(125))
    assert x.shape == (N,)
    assert np.isfinite(x).all()
    assert np.sqrt(np.mean(np.abs(x) ** 2)) == pytest.approx(1, abs=1e-6)


def test_generator_rejects_wfm_and_invalid_shapes():
    with pytest.raises(ValueError, match="Unsupported"):
        sample("WFM", np.random.default_rng(6), 10)
    with pytest.raises(ValueError, match="Unsupported"):
        sample("NFM", np.random.default_rng(6), 10, n=1024)
    with pytest.raises(ValueError, match="Unknown"):
        negative("not-a-test", np.random.default_rng(6))
