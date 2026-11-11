"""SYNTHETIC ONLY: diverse UNKNOWN training examples, not RF validation.

CW without keying and frequency sweeps may have ambiguous labels; never use
these as evidence for operational mode identification.
"""
from __future__ import annotations
import numpy as np

N, FS = 2048, 48000
FAMILIES = ("colored", "impulses", "sweep", "comb", "phase_noise")


def unknown_iq(rng: np.random.Generator, family: str | None = None) -> np.ndarray:
    if family is None:
        family = FAMILIES[int(rng.integers(len(FAMILIES)))]
    if family not in FAMILIES:
        raise ValueError(f"Unknown family: {family}")
    t = np.arange(N, dtype=float) / FS
    noise = (rng.normal(size=N) + 1j*rng.normal(size=N)) / np.sqrt(2)
    if family == "colored":
        # Recursive coloring: independent implementation of validation 2-tap filter.
        alpha = float(rng.uniform(0.6, 0.96))
        z = np.empty(N, dtype=np.complex128)
        z[0] = noise[0]
        for i in range(1, N):
            z[i] = alpha*z[i-1] + (1-alpha)*noise[i]
    elif family == "impulses":
        z = 0.07*noise
        for _ in range(int(rng.integers(3, 19))):
            k = int(rng.integers(N))
            width = int(rng.integers(1, 12))
            z[k:min(N, k+width)] += (rng.normal()+1j*rng.normal())*rng.uniform(1, 14)
    elif family == "sweep":
        f = rng.uniform(-7000, -2500) + rng.uniform(4000, 13000)*np.sin(2*np.pi*rng.uniform(3,20)*t)
        z = np.exp(2j*np.pi*np.cumsum(f)/FS) + .03*noise
    elif family == "comb":
        z = np.zeros(N, dtype=np.complex128)
        spacing, center = rng.uniform(750,1900), rng.uniform(-900,900)
        for k in range(-4,5):
            z += rng.uniform(.2,1)*np.exp(2j*np.pi*(center+k*spacing)*t + 1j*rng.uniform(-np.pi,np.pi))
        z += .09*noise
    else:
        z = np.exp(1j*(2*np.pi*rng.uniform(-3000,3000)*t +
                       np.cumsum(rng.normal(scale=rng.uniform(.1,1.5),size=N)))) + .15*noise
    z = np.asarray(z, dtype=np.complex128)
    if not np.isfinite(z).all():
        raise ValueError("Nonfinite synthetic signal")
    z -= z.mean()
    rms = float(np.sqrt(np.mean(np.abs(z)**2)))
    if rms < 1e-8:
        raise ValueError("Degenerate synthetic signal")
    z /= rms
    return np.stack([z.real,z.imag]).astype(np.float32)
