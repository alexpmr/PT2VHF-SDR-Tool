"""Regression: raw IQ carrier survives recording, receiver keeps legacy DC fix.

All tones below are synthetic. A DC component is not evidence of RF:
zero-IF receiver hardware can also generate a DC spur.
"""
import json
import wave

import numpy as np
import pytest

from pt2vhf.dsp.iq_classifier import IQClassifier, SAMPLES
from pt2vhf.iq_provenance import sha256_file, sidecar_path
from scripts.prepare_iq_rf_capture import convert


def make_engine():
    from pt2vhf.engine import Engine
    from pt2vhf.dsp.receiver import Receiver

    class SyntheticSource:
        sample_rate = 240_000
        center_freq = 145_500_000
        name = "SYNTHETIC_DC_TEST"
        dropped = 0

    engine = Engine()
    engine.source = SyntheticSource()
    engine.rx = Receiver(240_000)
    return engine


def read_iq(wav_path):
    with wave.open(str(wav_path), "rb") as wav:
        frames = wav.getnframes()
        samples = np.frombuffer(wav.readframes(frames), dtype="<i2").reshape(-1, 2)
    return (samples[:, 0].astype(np.float32)
            + 1j * samples[:, 1].astype(np.float32)) / 32768


def record_block(tmp_path, samples):
    eng = make_engine()
    receiver_means = []
    eng.iq_listeners.append(lambda iq, _center, _rate: receiver_means.append(np.mean(iq)))
    path = eng.start_iq_recording(str(tmp_path))
    eng.process_block(samples)
    eng.stop_iq_recording()
    return path, receiver_means


def test_zero_beat_cw_carrier_preserved_raw_but_receiver_corrected(tmp_path):
    carrier = np.full(16384, .28 + .17j, dtype=np.complex64)
    path, receiver_means = record_block(tmp_path, carrier)
    saved = read_iq(path)
    assert len(saved) == len(carrier)
    assert abs(np.mean(saved - carrier)) < 2 / 32768
    assert abs(np.mean(saved)) > .20
    assert receiver_means
    assert abs(receiver_means[0]) < 1e-5
    sidecar = json.loads(sidecar_path(path).read_text(encoding="utf-8"))
    assert sidecar["dc_removed_per_processing_block"] is False
    assert sidecar["iq_samples_kind"] == "raw_before_receiver_dc_correction"
    assert sidecar["hardware_dc_spur_possible"] is True
    assert sidecar["wav_sha256"] == sha256_file(path)


def test_centered_am_modulated_carrier_survives_iq_wav_and_48k_conversion(tmp_path):
    fs = 240_000
    t = np.arange(48000, dtype=np.float64) / fs
    iq = (.28 * (1 + .55*np.sin(2*np.pi*800*t))
          * np.exp(.35j)).astype(np.complex64)
    raw_path, receiver_means = record_block(tmp_path, iq)
    recorded = read_iq(raw_path)
    assert abs(np.mean(recorded)) > .20
    assert abs(receiver_means[0]) < 1e-5
    channel = tmp_path / "am_channel48.wav"
    result = convert(raw_path, channel, None, 145_500_000)
    assert result["capture_integrity_verified"]
    output = read_iq(channel)
    assert len(output) == 9600
    assert abs(np.mean(output[300:-300])) > .20
    assert float(np.std(np.abs(output[300:-300]))) > .01


def test_iq_input_is_not_mutated_when_receiver_removes_dc(tmp_path):
    rng = np.random.default_rng(9)
    iq = (.23 + .08j + .03 * (rng.normal(size=16384)
            + 1j * rng.normal(size=16384))).astype(np.complex64)
    original = iq.copy()
    path, _ = record_block(tmp_path, iq)
    np.testing.assert_array_equal(iq, original)
    saved = read_iq(path)
    assert np.abs(np.mean(saved) - np.mean(original)) < 2 / 32768


def test_legacy_onnx_contract_still_rejects_pure_zero_hz_carrier():
    # Existing models were trained on zero-mean samples. A perfectly static
    # complex tone is indistinguishable from hardware DC and becomes zero.
    x = np.full(SAMPLES, 0.3 + 0.2j, dtype=np.complex64)
    with pytest.raises(ValueError, match="No usable RF signal"):
        IQClassifier.features(x)


def test_am_envelope_preprocessing_still_uses_existing_zero_mean_contract():
    t = np.arange(SAMPLES) / 48_000
    am = (0.4 * (1 + 0.5*np.sin(2*np.pi*700*t))
          * np.exp(.15j)).astype(np.complex64)
    features = IQClassifier.features(am)
    complex_features = features[0, 0] + 1j * features[0, 1]
    assert features.shape == (1, 2, SAMPLES)
    assert abs(complex_features.mean()) < 1e-5
    assert np.isclose(np.sqrt(np.mean(abs(complex_features)**2)), 1, atol=2e-5)
