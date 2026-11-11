"""IQ dataset quality checks use generated PCM, not captures from radio hardware."""
import json
import wave
import numpy as np
import pytest
from scripts.audit_iq_dataset import inspect_recording, audit_dataset


def _wav(path, z, rate=48000):
    z = np.asarray(z, dtype=np.complex128)
    pcm = np.empty((len(z), 2), dtype="<i2")
    pcm[:, 0] = np.clip(np.round(z.real * 32767), -32768, 32767).astype("<i2")
    pcm[:, 1] = np.clip(np.round(z.imag * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def _noise(n=2048*15, seed=42):
    rng = np.random.default_rng(seed)
    return .1 * (rng.normal(size=n) + 1j*rng.normal(size=n))


def _manifest(root, rows):
    m = root/"manifest.json"
    m.write_text(json.dumps({"recordings": rows}), encoding="utf8")
    return m


def _row(name, session, mode="NFM"):
    return {"path": name, "session_id": session, "mode": mode,
            "device": "SYNTHETIC", "frequency_hz": 145500000}


def test_clean_iq_no_private_names_in_report(tmp_path):
    _wav(tmp_path/"good.wav", _noise())
    m = _manifest(tmp_path, [_row("good.wav", "private-session")])
    report = audit_dataset(m, tmp_path)
    assert report["status"] == "PASS"
    assert not report["rf_validated"]
    serialized = json.dumps(report)
    assert "private-session" not in serialized
    assert "good.wav" not in serialized
    assert "_fingerprints" not in serialized


def test_silence_and_clipping_are_blocked(tmp_path):
    _wav(tmp_path/"silent.wav", np.zeros(2048*12, np.complex64))
    report = audit_dataset(_manifest(tmp_path, [_row("silent.wav", "s1")]), tmp_path)
    assert report["status"] == "BLOCK"
    assert "BLOCK: almost_all_windows_quiet" in report["entries"][0]["flags"]
    _wav(tmp_path/"clipped.wav", np.full(2048*12, 1+1j))
    report = audit_dataset(_manifest(tmp_path, [_row("clipped.wav", "s2")]), tmp_path)
    assert report["status"] == "BLOCK"
    assert "BLOCK: heavy_adc_or_pcm_clipping" in report["entries"][0]["flags"]


def test_reused_samples_across_sessions_are_blocked(tmp_path):
    signal = _noise()
    _wav(tmp_path/"a.wav", signal)
    _wav(tmp_path/"b.wav", signal)
    report = audit_dataset(_manifest(tmp_path, [_row("a.wav", "s1"), _row("b.wav", "s2")]),
                           tmp_path)
    assert report["blocked_recordings"] == 2
    assert all("BLOCK: identical_iq_window_across_sessions" in e["flags"]
               for e in report["entries"])


def test_repeated_windows_inside_same_session_are_not_data_leakage(tmp_path):
    z = _noise()
    _wav(tmp_path/"a.wav", z)
    _wav(tmp_path/"b.wav", z)
    report = audit_dataset(_manifest(tmp_path, [_row("a.wav", "s1"), _row("b.wav", "s1")]),
                           tmp_path)
    assert report["status"] == "PASS"


def test_stereo_audio_masquerading_as_iq_is_reviewed(tmp_path):
    rng = np.random.default_rng(23)
    mono = .1*rng.normal(size=2048*15)
    _wav(tmp_path/"audio.wav", mono+1j*mono)
    report = audit_dataset(_manifest(tmp_path, [_row("audio.wav", "s1")]), tmp_path)
    assert report["status"] == "REVIEW"
    assert "REVIEW: suspicious_stereo_channel_correlation" in report["entries"][0]["flags"]


def test_am_carrier_at_dc_is_not_rejected(tmp_path):
    t = np.arange(2048*15)/48000
    z = .4 + .09*np.sin(2*np.pi*1900*t)
    _wav(tmp_path/"am.wav", z)
    report = audit_dataset(_manifest(tmp_path, [_row("am.wav", "s1", "AM")]), tmp_path)
    assert report["status"] == "REVIEW"
    assert report["blocked_recordings"] == 0
    assert "REVIEW: centered_carrier_or_hardware_dc_spur" in report["entries"][0]["flags"]


def test_short_recording_reviewed(tmp_path):
    _wav(tmp_path/"short.wav", _noise(n=2048*4))
    report = audit_dataset(_manifest(tmp_path, [_row("short.wav", "s1")]), tmp_path)
    assert "REVIEW: short_recording" in report["entries"][0]["flags"]


def test_invalid_sample_rate_and_empty_rejected(tmp_path):
    _wav(tmp_path/"bad.wav", _noise(), rate=44100)
    with pytest.raises(ValueError, match="48 kHz"):
        inspect_recording(tmp_path/"bad.wav")
    _wav(tmp_path/"short.wav", _noise(n=1000))
    with pytest.raises(ValueError, match="no complete"):
        inspect_recording(tmp_path/"short.wav")
    with pytest.raises(ValueError, match="max_windows"):
        inspect_recording(tmp_path/"short.wav", max_windows=0)



def test_pure_zero_beat_cw_needs_human_review_not_false_block(tmp_path):
    # A hardware DC spur has the same mathematical IQ samples.
    raw = np.full(2048*15, .28 + .17j, dtype=np.complex64)
    _wav(tmp_path/"cw.wav", raw)
    report = audit_dataset(_manifest(tmp_path, [_row("cw.wav", "s1", "CW")]), tmp_path)
    assert report["status"] == "REVIEW"
    assert report["blocked_recordings"] == 0
    flags = report["entries"][0]["flags"]
    assert "REVIEW: constant_cw_am_or_hardware_dc" in flags
    assert "REVIEW: centered_carrier_or_hardware_dc_spur" in flags
    assert not report["rf_validated"]
    assert not report["operator_labels_verified"]


def test_constant_unknown_remains_blocked_as_invalid_classification_sample(tmp_path):
    raw = np.full(2048*15, .28 + .17j, dtype=np.complex64)
    _wav(tmp_path/"unknown.wav", raw)
    report = audit_dataset(
        _manifest(tmp_path, [_row("unknown.wav", "s1", "UNKNOWN")]), tmp_path)
    assert report["status"] == "BLOCK"
    assert "BLOCK: nearly_constant_iq_samples" in report["entries"][0]["flags"]


def test_full_duration_sampling_catches_late_clipping(tmp_path):
    # The old prefix-only QA inspected 16 clean windows and falsely passed.
    first = _noise(n=2048*20, seed=811)
    tail = np.full(2048*60, 1+1j, dtype=np.complex64)
    _wav(tmp_path/"late_clip.wav", np.concatenate((first, tail)))
    report = audit_dataset(
        _manifest(tmp_path, [_row("late_clip.wav", "s1")]), tmp_path,
        max_windows=16)
    entry = report["entries"][0]
    assert report["status"] == "BLOCK"
    assert "BLOCK: heavy_adc_or_pcm_clipping" in entry["flags"]
    assert entry["metrics"]["windows_available"] == 80
    assert entry["metrics"]["windows_inspected"] == 16
    assert entry["metrics"]["window_selection"] == "uniform_full_recording_nonoverlapping"


def test_full_duration_sampling_detects_late_cross_session_reuse(tmp_path):
    # Two independent-looking prefixes, but an exact copied IQ window at end.
    first = _noise(n=2048*80, seed=301)
    second = _noise(n=2048*80, seed=302)
    second[-2048:] = first[-2048:]
    _wav(tmp_path/"a.wav", first)
    _wav(tmp_path/"b.wav", second)
    report = audit_dataset(
        _manifest(tmp_path, [_row("a.wav", "s1"), _row("b.wav", "s2")]),
        tmp_path, max_windows=16)
    assert report["blocked_recordings"] == 2
    assert all("BLOCK: identical_iq_window_across_sessions" in e["flags"]
               for e in report["entries"])


def test_single_window_sampling_and_no_duplicate_indices(tmp_path):
    _wav(tmp_path/"short.wav", _noise(n=2048*17, seed=303))
    one = inspect_recording(tmp_path/"short.wav", max_windows=1)
    all_windows = inspect_recording(tmp_path/"short.wav", max_windows=100)
    assert one["windows_inspected"] == 1
    assert one["windows_available"] == 17
    assert all_windows["windows_inspected"] == 17
