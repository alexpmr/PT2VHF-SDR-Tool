"""Synthetic-only regression: session RF gate must reject contradictory classifier metadata.

These IQ tones are generated in memory. No real RF or neural model is used.
"""
import wave

import numpy as np
import pytest

from pt2vhf.dsp.iq_classifier import CLASSES, Classification
from scripts.iq_session_gate import observations


def _synthetic_wav(path):
    t = np.arange(4096) / 48000
    tone = (12000 * np.sin(2 * np.pi * 1400 * t)).astype("<i2")
    pcm = np.stack((tone, tone // 2), axis=1)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(pcm.tobytes())


def _observe(tmp_path, *, mode="AM", confidence=.85, gate=None):
    path = tmp_path / "synthetic.wav"
    _synthetic_wav(path)

    class Stub:
        def __init__(self):
            if gate is not None:
                self.min_confidence = gate

        def predict(self, iq):
            probabilities = {name: 0.0 for name in CLASSES}
            probabilities["AM"] = .85
            probabilities["UNKNOWN"] = .15
            return Classification(mode, confidence, probabilities)

    return observations([(path, "AM", "synthetic-session", "synthetic-SDR")],
                        Stub(), max_windows=2)


@pytest.mark.parametrize("mode,confidence,gate,message", [
    ("AM", .5, None, "confidence disagrees"),
    ("AM", float("nan"), None, "Invalid model confidence"),
    ("AM", float("inf"), None, "Invalid model confidence"),
    ("AM", True, None, "Invalid model confidence"),
    ("AM", "0.85", None, "Invalid model confidence"),
    ("NFM", .85, None, "mode disagrees with softmax"),
    ("INVALID", .85, None, "Invalid classifier mode"),
    (None, .85, None, "Invalid classifier mode"),
    ("AM", .85, .90, "configured confidence gate"),
    ("UNKNOWN", .85, .80, "configured confidence gate"),
    ("AM", .85, float("nan"), "Invalid classifier confidence threshold"),
    ("AM", .85, True, "Invalid classifier confidence threshold"),
])
def test_rejects_inconsistent_classifier_metadata(
        tmp_path, mode, confidence, gate, message):
    with pytest.raises(ValueError, match=message):
        _observe(tmp_path, mode=mode, confidence=confidence, gate=gate)


@pytest.mark.parametrize("mode,gate", [
    ("AM", .80),
    ("UNKNOWN", .90),
])
def test_valid_effective_mode_and_raw_threshold_calibration_remain_separate(
        tmp_path, mode, gate):
    rows = _observe(tmp_path, mode=mode, gate=gate)
    assert len(rows) == 2
    # The threshold calibration always records the raw softmax winner,
    # even when the classifier correctly abstains at a stricter gate.
    assert all(row[:3] == ("AM", "AM", .85) for row in rows)


def test_numpy_confidence_is_valid(tmp_path):
    rows = _observe(tmp_path, confidence=np.float32(.85), gate=np.float64(.8))
    assert len(rows) == 2
    assert all(row[2] == .85 for row in rows)
