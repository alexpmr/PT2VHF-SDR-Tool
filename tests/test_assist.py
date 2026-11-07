import numpy as np
import pytest

from pt2vhf.dsp.assist import adaptive_passband, detect_mode, estimate_ssb_offset
from tests.synth_signals import FS, am, cw, noise, nfm, ssb240, voice_ssb, wfm


@pytest.mark.parametrize("delta,sb,f0,snr", [(0, "USB", 120, 20), (137, "USB", 110, 20), (-250, "USB", 180, 20),
                                             (420, "USB", 100, 20), (-90, "LSB", 130, 20), (200, "USB", 120, 6)])
def test_ssb_autotune(delta, sb, f0, snr):
    x = voice_ssb(delta=delta, lsb=(sb == "LSB"), f0base=f0, seed=abs(delta) + 3, snr_db=snr)
    r = estimate_ssb_offset(x, 48000, sb)
    assert r is not None and abs(r[0] - delta) <= 15


def test_ssb_autotune_rejects_non_voice():
    rng = np.random.default_rng(1)
    n = (rng.normal(size=192000) + 1j * rng.normal(size=192000)).astype(np.complex64)
    assert estimate_ssb_offset(n, 48000, "USB") is None
    t = np.arange(192000) / 48000
    carrier = (np.exp(2j * np.pi * 1000 * t) + 0.05 * n).astype(np.complex64)
    assert estimate_ssb_offset(carrier, 48000, "USB") is None


@pytest.mark.parametrize("name,expected", [("nfm", "NFM"), ("wfm", "WFM"), ("am", "AM"), ("cw", "CW"),
                                           ("usb", "USB"), ("lsb", "LSB")])
def test_detect_mode(name, expected):
    x = {"nfm": nfm, "wfm": wfm, "am": am, "cw": cw}.get(name, lambda: ssb240(lsb=(name == "lsb")))()
    x = (x + noise(len(x), 0.01, 1)).astype(np.complex64)
    g = detect_mode(x, FS, 14.2e6 if name == "lsb" else 7.1e6)  # SSB contra a convenção da faixa
    assert g is not None and g.mode == expected
    if expected in ("USB", "LSB"):
        assert abs(g.center_offset) < 20


def test_detect_mode_noise_and_offset():
    assert detect_mode(noise(FS, 1).astype(np.complex64), FS) is None
    g = detect_mode((nfm(off=2000) + noise(FS, 0.01)).astype(np.complex64), FS)
    assert g.mode == "NFM" and abs(g.center_offset - 2000) < 300
    g = detect_mode((ssb240(delta=250) + noise(2 * FS, 0.01)).astype(np.complex64), FS, 14.2e6)
    assert g.mode == "USB" and abs(g.center_offset - 250) < 20


def test_adaptive_passband():
    x = (nfm() + noise(FS, 0.01)).astype(np.complex64)
    lo, hi = adaptive_passband(x, FS, "NFM", -6000, 6000)
    assert 6000 < hi < 12000 and lo == -hi
    x = (ssb240() + noise(2 * FS, 0.01)).astype(np.complex64)
    lo, hi = adaptive_passband(x, FS, "USB", 300, 2800)
    assert 100 <= lo < 400 and 2700 < hi < 3300
