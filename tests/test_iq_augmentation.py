"""CPU-only tests of training perturbations; also run in the normal non-Torch CI."""
import numpy as np
import pytest

from scripts.iq_augmentation import augment_iq


def _iq():
    n = np.arange(2048)
    z = np.exp(2j * np.pi * n * 300 / 2048).astype(np.complex64)
    return np.stack([z.real, z.imag]).astype("float32")


def test_augmentation_repeatable_and_does_not_modify_input():
    data = _iq()
    before = data.copy()
    a = augment_iq(data, np.random.default_rng(101))
    b = augment_iq(data, np.random.default_rng(101))
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(data, before)
    assert a.shape == (2, 2048)
    assert a.dtype == np.float32
    assert np.isfinite(a).all()
    assert float(np.sqrt(np.mean(a[0] ** 2 + a[1] ** 2))) == pytest.approx(1, abs=1e-6)
    assert np.linalg.norm(a.mean(axis=1)) < 1e-5


@pytest.mark.parametrize("wrong", [
    np.zeros((2, 1024), dtype=np.float32),
    np.zeros((2048, 2), dtype=np.float32),
    np.full((2, 2048), np.nan, dtype=np.float32),
    np.zeros((2, 2048), dtype=np.float32),
])
def test_bad_iq_is_rejected(wrong):
    with pytest.raises(ValueError):
        augment_iq(wrong, np.random.default_rng(2))
