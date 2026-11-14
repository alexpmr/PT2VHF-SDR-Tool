"""Synthetic-only regression for intra-split IQ excerpt reuse.

No RF capture or operational accuracy is asserted by these fixtures.
"""
import json
import wave

import numpy as np
import pytest

from scripts.iq_session_gate import audit


def _pcm(seed):
    return np.random.default_rng(seed).integers(
        -12000, 12000, size=(4096, 2), dtype=np.int16
    ).tobytes()


def _wav(path, pcm):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(pcm)


def _manifest(root, split, seeds):
    rows = []
    for index, (mode, seed) in enumerate(zip(("AM", "UNKNOWN"), seeds)):
        name = f"{split}-{index}.wav"
        _wav(root / name, _pcm(seed))
        rows.append({
            "path": name,
            "mode": mode,
            "session_id": f"{split}-{index}",
            "device": "synthetic-sdr",
            "frequency_hz": 145500000,
        })
    path = root / f"{split}.json"
    path.write_text(json.dumps({"recordings": rows}), encoding="utf-8")
    return path


@pytest.mark.parametrize("split", ("calibration", "holdout"))
def test_audit_rejects_partial_iq_excerpt_reused_within_split(tmp_path, split):
    cal = _manifest(tmp_path, "calibration", (11, 12))
    hold = _manifest(tmp_path, "holdout", (21, 22))
    manifest = cal if split == "calibration" else hold
    original = tmp_path / f"{split}-0.wav"
    with wave.open(str(original), "rb") as source:
        copied_window = source.readframes(2048)
    # Second half differs: the new WAV is not a whole-file SHA-256 duplicate.
    fresh_window = _pcm(33)[2048 * 4:]
    new_name = f"{split}-excerpt.wav"
    _wav(tmp_path / new_name, copied_window + fresh_window)
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["recordings"].append({
        "path": new_name,
        "mode": "AM",
        "session_id": f"{split}-independent-claimed",
        "device": "synthetic-sdr",
        "frequency_hz": 145500000,
    })
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match=f"Identical IQ window within {split} split"):
        audit(cal, hold, tmp_path)


def test_audit_allows_distinct_iq_windows_and_repeats_within_one_wav(tmp_path):
    cal = _manifest(tmp_path, "calibration", (11, 12))
    hold = _manifest(tmp_path, "holdout", (21, 22))
    # Repetition *within one file* is not an inter-recording independence leak.
    repeated = _pcm(33)[:2048 * 4]
    _wav(tmp_path / "calibration-0.wav", repeated + repeated)
    calibration, holdout = audit(cal, hold, tmp_path)
    assert len(calibration) == 2
    assert len(holdout) == 2
