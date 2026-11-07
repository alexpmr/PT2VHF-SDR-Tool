import numpy as np
import pytest

from pt2vhf.dsp.filters import Decimator, FIRFilter, bandpass_complex_taps
from pt2vhf.dsp.receiver import AUDIO_RATE, Receiver, compute_spectrum


def tone_freq(x, fs):
    x = x - np.mean(x)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.argmax(spec) * fs / len(x)


def test_fir_blockwise_equals_whole():
    rng = np.random.default_rng(0)
    x = rng.normal(size=20000).astype(np.float32)
    taps = np.hanning(63).astype(np.float32)
    whole = np.convolve(x, taps)[:len(x)]
    f = FIRFilter(taps)
    parts = np.concatenate([f.process(x[i:i + 1777]) for i in range(0, len(x), 1777)])
    assert np.allclose(parts, whole, atol=1e-3)


def test_decimator_blockwise_phase():
    x = np.arange(10000, dtype=np.float32)
    d1 = Decimator(5)
    whole = d1.process(x)
    d2 = Decimator(5)
    parts = np.concatenate([d2.process(x[i:i + 333]) for i in range(0, len(x), 333)])
    assert len(parts) == len(whole)
    assert np.allclose(parts, whole, rtol=1e-4)


def test_complex_bandpass_selects_usb():
    fs = 48000
    taps = bandpass_complex_taps(fs, 300, 2800)
    n = np.arange(fs)
    up = np.exp(2j * np.pi * 1500 * n / fs)
    down = np.exp(-2j * np.pi * 1500 * n / fs)
    assert np.std(np.convolve(up, taps, "valid")) > 0.9
    assert np.std(np.convolve(down, taps, "valid")) < 0.01


def _iq_fm_tone(fs, n, off, tone, dev):
    t = np.arange(n) / fs
    ph = 2 * np.pi * np.cumsum(off + dev * np.sin(2 * np.pi * tone * t)) / fs
    return (0.3 * np.exp(1j * ph)).astype(np.complex64)


@pytest.mark.parametrize("mode,tone", [("NFM", 1000.0), ("WFM", 3000.0)])
def test_fm_demod_recovers_tone(mode, tone):
    fs = 1_200_000
    rx = Receiver(fs)
    rx.set_mode(mode)
    rx.set_offset(100_000)
    iq = _iq_fm_tone(fs, fs, 100_000, tone, 3000 if mode == "NFM" else 50_000)
    out = np.concatenate([rx.process(iq[i:i + 65536])[0] for i in range(0, len(iq), 65536)])
    assert len(out) == pytest.approx(AUDIO_RATE, rel=0.01)
    assert tone_freq(out[4800:], AUDIO_RATE) == pytest.approx(tone, abs=15)


def test_am_and_usb():
    fs = 240_000
    t = np.arange(fs) / fs
    rx = Receiver(fs)
    rx.set_mode("AM")
    rx.set_offset(20_000)
    iq = ((1 + 0.5 * np.sin(2 * np.pi * 800 * t)) * np.exp(2j * np.pi * 20_000 * t)).astype(np.complex64) * 0.1
    out = rx.process(iq)[0]
    assert tone_freq(out[4800:], AUDIO_RATE) == pytest.approx(800, abs=10)

    rx.set_mode("USB")
    iq = (0.1 * np.exp(2j * np.pi * (20_000 + 1200) * t)).astype(np.complex64)
    out = rx.process(iq)[0]
    assert tone_freq(out[4800:], AUDIO_RATE) == pytest.approx(1200, abs=10)


def test_squelch_mutes_noise():
    fs = 240_000
    rng = np.random.default_rng(3)
    rx = Receiver(fs)
    rx.squelch.threshold_db = -20
    noise = (rng.normal(0, 1e-3, fs) + 1j * rng.normal(0, 1e-3, fs)).astype(np.complex64)
    out = rx.process(noise)[0]
    assert not rx.squelch.is_open
    assert np.max(np.abs(out)) == 0


def test_spectrum_peak_position():
    fs, n = 1_200_000, 4096
    t = np.arange(n * 4) / fs
    x = np.exp(2j * np.pi * 300_000 * t).astype(np.complex64)
    s = compute_spectrum(x, n)
    peak = np.argmax(s)
    assert (peak - n / 2) * fs / n == pytest.approx(300_000, abs=fs / n)
    assert s[peak] == pytest.approx(0, abs=1.0)  # 0 dBFS para tom de amplitude 1


def test_audio_chain_eq_nr_notch_agc():
    fs = 240_000
    t = np.arange(fs) / fs
    rng = np.random.default_rng(5)
    rx = Receiver(fs)
    rx.set_mode("USB")
    rx.set_offset(10_000)
    rx.eq.enabled = True
    rx.eq.set_gains([-10, -5, 0, 5, 5, 0, -5, -10])
    rx.nr.enabled = True
    rx.notch.enabled = True
    rx.notch.set_freq(1000)
    rx.nb.enabled = True
    iq = (0.05 * np.exp(2j * np.pi * (10_000 + 1000) * t) + 0.05 * np.exp(2j * np.pi * (10_000 + 1700) * t)
          + 0.001 * (rng.normal(size=fs) + 1j * rng.normal(size=fs))).astype(np.complex64)
    out = np.concatenate([rx.process(iq[i:i + 24000])[0] for i in range(0, fs, 24000)])
    assert np.all(np.isfinite(out)) and np.max(np.abs(out)) <= 1.0
    # notch em 1 kHz: sobra o tom de 1700 Hz
    assert tone_freq(out[len(out) // 2:], AUDIO_RATE) == pytest.approx(1700, abs=15)
