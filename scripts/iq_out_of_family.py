"""Independent *synthetic* IQ holdout generator (not the training generator).

At 48 kS/s with 2048 IQ points, occupied channel bandwidth is too narrow
to represent a conventional wideband broadcast FM signal faithfully.
WFM is explicitly NOT validated by this benchmark.
"""
from __future__ import annotations

import numpy as np

FS = 48_000
N = 2048
SUPPORTED = ("CW", "AM", "NFM", "USB", "LSB", "UNKNOWN")
NEGATIVES = ("unmodulated_carrier", "frequency_chirp", "multi_carrier", "impulsive_noise")


def _normalize(z):
    z = np.asarray(z, dtype=np.complex128)
    if z.shape != (N,) or not np.isfinite(z).all():
        raise ValueError("Invalid synthetic IQ samples")
    z -= z.mean()
    rms = np.sqrt(np.mean(np.abs(z) ** 2))
    if rms < 1e-8:
        raise ValueError("Empty synthetic IQ")
    return (z / rms).astype(np.complex64)


def _audio(rng, t):
    # Different from the training oscillator family: changing tone count,
    # phases, amplitudes and a slow, correlated amplitude envelope.
    z = np.zeros(t.size, dtype=np.float64)
    for _ in range(int(rng.integers(2, 6))):
        tone = float(rng.uniform(160, 2600))
        z += float(rng.uniform(0.2, 1.0)) * np.sin(2 * np.pi * tone * t + rng.uniform(-np.pi, np.pi))
    z /= max(float(np.max(np.abs(z))), 1e-8)
    return z


def sample(mode: str, rng: np.random.Generator, snr_db: float, *, n: int = N) -> np.ndarray:
    """Generate labelled IQ, introducing noise at the specified measured SNR."""
    if mode not in SUPPORTED or n != N:
        raise ValueError(f"Unsupported narrowband class or sample count: {mode}")
    t = np.arange(N, dtype=np.float64) / FS
    phase = float(rng.uniform(-np.pi, np.pi))
    offset = float(rng.uniform(-170, 170))
    audio = _audio(rng, t)
    if mode == "CW":
        # Short 42-ms snapshot can contain partial Morse elements, unlike
        # the generator's regularly gated CW: deliberate distribution shift.
        key_rate = float(rng.uniform(8, 31))
        gate = (np.sin(2 * np.pi * key_rate * t + phase) > float(rng.uniform(-0.6, 0.5))).astype(float)
        z = gate * np.exp(2j * np.pi * (offset + rng.uniform(350, 3400)) * t + 1j * phase)
    elif mode == "AM":
        depth = float(rng.uniform(0.18, 0.9))
        envelope = 1 + depth * audio
        z = envelope * np.exp(2j * np.pi * offset * t + 1j * phase)
    elif mode == "NFM":
        deviation = float(rng.uniform(1500, 4300))
        instantaneous_freq = offset + deviation * audio
        z = np.exp(1j * (2 * np.pi * np.cumsum(instantaneous_freq) / FS + phase))
    elif mode in ("USB", "LSB"):
        sign = 1 if mode == "USB" else -1
        z = np.zeros(N, dtype=np.complex128)
        for _ in range(int(rng.integers(3, 8))):
            freq = float(rng.uniform(330, 3200))
            z += rng.uniform(0.15, 0.85) * np.exp(
                1j * (2 * np.pi * (offset + sign * freq) * t + rng.uniform(-np.pi, np.pi)))
    else:
        noise = rng.normal(size=N) + 1j * rng.normal(size=N)
        # Colored noise, different from independent white-noise training UNKNOWN.
        z = 0.65 * noise + 0.35 * np.roll(noise, 1)
    z = np.asarray(z, dtype=np.complex128)
    rms = np.sqrt(np.mean(np.abs(z) ** 2))
    noise = (rng.normal(size=N) + 1j * rng.normal(size=N)) / np.sqrt(2)
    z += rms * 10 ** (-snr_db / 20) * noise
    return _normalize(z)


def negative(kind: str, rng: np.random.Generator):
    """Out-of-distribution inputs WITHOUT a reliable seven-class label."""
    t = np.arange(N, dtype=np.float64) / FS
    if kind == "unmodulated_carrier":
        z = np.exp(2j * np.pi * rng.uniform(300, 4000) * t + 1j * rng.uniform(0, 2 * np.pi))
    elif kind == "frequency_chirp":
        a, b = float(rng.uniform(-9000, -3000)), float(rng.uniform(3000, 9000))
        z = np.exp(2j * np.pi * (a * t + 0.5 * (b - a) / t[-1] * t ** 2))
    elif kind == "multi_carrier":
        z = np.zeros(N, dtype=np.complex128)
        for _ in range(12):
            z += np.exp(2j * np.pi * rng.uniform(-9000, 9000) * t + 1j * rng.uniform(0, 2 * np.pi))
    elif kind == "impulsive_noise":
        z = (rng.normal(size=N) + 1j * rng.normal(size=N)) * 0.03
        inds = rng.choice(N, size=12, replace=False)
        z[inds] += (rng.normal(size=12) + 1j * rng.normal(size=12)) * 15
    else:
        raise ValueError(f"Unknown negative condition: {kind}")
    return _normalize(z)
