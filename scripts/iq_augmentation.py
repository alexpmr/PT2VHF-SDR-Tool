"""Deterministic, label-preserving synthetic IQ augmentations for research.

These augmentations are NOT a realistic substitute for SDR IQ recordings.
Keep the stress benchmark separate to avoid tuning directly to its exact inputs.
"""
from __future__ import annotations

import numpy as np

FS = 48_000


def augment_iq(iq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return normalized float32 I/Q [2, 2048] without mutating the input.

    Adds independent random phase, gain, frequency drift, I/Q skew and noise.
    Identically applied to all labels to avoid leaking the class via augmentation.
    """
    src = np.asarray(iq, dtype=np.float32)
    if src.shape != (2, 2048) or not np.isfinite(src).all():
        raise ValueError("Expected finite I/Q with shape [2, 2048]")
    z = src[0].astype(np.float64) + 1j * src[1].astype(np.float64)
    initial_rms = float(np.sqrt(np.mean(np.abs(z) ** 2)))
    if initial_rms < 1e-8:
        raise ValueError("Cannot augment empty IQ signal")

    phase = rng.uniform(-np.pi, np.pi)
    gain = rng.uniform(0.55, 1.6)
    z *= gain * np.exp(1j * phase)

    if rng.random() < 0.78:
        cfo_hz = rng.uniform(-380, 380)
        t = np.arange(z.size, dtype=np.float64) / FS
        z *= np.exp(2j * np.pi * cfo_hz * t)

    if rng.random() < 0.65:
        imbalance = rng.uniform(0.76, 1.25)
        leakage = rng.uniform(-0.15, 0.15)
        z = z.real + 1j * (imbalance * z.imag + leakage * z.real)

    if rng.random() < 0.5:
        z += rng.uniform(-0.25, 0.25) + 1j * rng.uniform(-0.25, 0.25)

    if rng.random() < 0.66:
        # Additional AWGN measured relative to the actual IQ power BEFORE noise.
        extra_snr_db = rng.uniform(-6, 20)
        power = float(np.mean(np.abs(z) ** 2))
        noise = (rng.normal(size=z.size) + 1j * rng.normal(size=z.size)) / np.sqrt(2)
        z += np.sqrt(power) * (10 ** (-extra_snr_db / 20)) * noise

    z -= z.mean()
    rms = float(np.sqrt(np.mean(np.abs(z) ** 2)))
    if not np.isfinite(rms) or rms < 1e-8:
        raise ValueError("Augmentation yielded invalid IQ power")
    z /= rms
    return np.stack([z.real, z.imag], axis=0).astype(np.float32)
