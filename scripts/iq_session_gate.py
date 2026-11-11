"""Research-only IQ/ONNX threshold selection with disjoint capture sessions.

Do not treat windows from a single capture as independent RF measurements.
No automatic receiver tuning or production promotion is authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path

from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier
from scripts.evaluate_iq_recordings import read_manifest, read_windows

THRESHOLDS = (0.80, 0.90, 0.95, 0.99, 0.999)


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def sampled_iq_window_hashes(path: Path, edge_windows: int = 16) -> set[bytes]:
    """Sample first/middle/last nonzero IQ windows for partial leakage detection.

    Only exact byte-for-byte 2048-IQ-sample matches are caught. Edited,
    rechannelized or time-shifted reuse still needs human provenance checks.
    """
    if edge_windows < 1:
        raise ValueError("edge_windows must be positive")
    result = set()
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(),
                wav.getcomptype()) != (2, 2, 48000, "NONE"):
            raise ValueError("Split audit requires stereo 48k PCM16 IQ WAV")
        count = wav.getnframes() // 2048
        # Include the middle of long recordings: trimming or concatenating
        # a capture can reuse an interior window while changing both edges.
        # This remains a bounded exact-match audit, not a full leak proof.
        middle_start = max(0, (count - edge_windows) // 2)
        indices = sorted(set(range(min(edge_windows, count))) |
                         set(range(middle_start, min(count, middle_start + edge_windows))) |
                         set(range(max(0, count-edge_windows), count)))
        for index in indices:
            wav.setpos(index * 2048)
            raw = wav.readframes(2048)
            if len(raw) != 8192:
                raise ValueError("Truncated IQ sample window")
            if any(raw):  # all-zero samples have no diagnostic uniqueness
                result.add(hashlib.sha256(raw).digest())
    return result


def audit(cal_manifest: Path, hold_manifest: Path, root: Path):
    cal, hold = read_manifest(cal_manifest, root), read_manifest(hold_manifest, root)
    if len(cal) + len(hold) > 2000:
        raise ValueError("Too many recordings in the evaluation")
    if {r[2] for r in cal} & {r[2] for r in hold}:
        raise ValueError("Overlapping calibration and holdout sessions")
    if {r[0] for r in cal} & {r[0] for r in hold}:
        raise ValueError("Overlapping WAV paths")
    if {digest(r[0]) for r in cal} & {digest(r[0]) for r in hold}:
        raise ValueError("Identical WAV content across split: recording leakage")
    # Different WAVs may still contain an identical excerpt (e.g., trimming
    # or appending a tail). Prevent exact sample reuse across split sessions.
    calibration_windows = set()
    for source, *_ in cal:
        calibration_windows.update(sampled_iq_window_hashes(source))
    for source, *_ in hold:
        if calibration_windows & sampled_iq_window_hashes(source):
            raise ValueError("Identical IQ window across calibration/holdout: test leakage")
    for label, rows in (("calibration", cal), ("holdout", hold)):
        modes = {r[1] for r in rows}
        if len({r[2] for r in rows}) < 2 or "UNKNOWN" not in modes or len(modes) == 1:
            raise ValueError(label + " requires separate known and UNKNOWN sessions")
    return cal, hold


def observations(rows, model, max_windows, *, accounting=None):
    if max_windows < 1:
        raise ValueError("max_windows must be positive")
    data = []
    selected_total = silent_total = rejected_total = inferred_total = 0
    per_session = {}
    for path, label, session, _device in rows:
        found = 0
        stats = {"selected": 0, "skipped_silence": 0}
        for iq in read_windows(path, max_windows, stats=stats):
            try:
                result = model.predict(iq)
            except ValueError as exc:
                if str(exc) != "No usable RF signal (DC-only or unresolved carrier)":
                    raise
                rejected_total += 1
                continue
            scores = result.probabilities
            if set(scores) != set(CLASSES):
                raise ValueError("Model label mismatch")
            if not all(math.isfinite(float(v)) and 0 <= float(v) <= 1
                       for v in scores.values()):
                raise ValueError("Invalid model probability")
            predicted = max(scores, key=scores.get)
            data.append((label, predicted, float(scores[predicted]), session))
            found += 1
        selected_total += stats["selected"]
        silent_total += stats["skipped_silence"]
        inferred_total += found
        session_counts = per_session.setdefault(session, [0, 0])
        session_counts[0] += stats["selected"]
        session_counts[1] += found
        if not found:
            raise ValueError("No inferred IQ windows in recording (silence/DC rejection)")
    if selected_total != silent_total + rejected_total + inferred_total:
        raise AssertionError("IQ gate window accounting mismatch")
    if accounting is not None:
        coverages = [inferred / selected for selected, inferred in per_session.values()
                     if selected]
        accounting.update({
            "windows_selected": selected_total,
            "windows_skipped_silence": silent_total,
            "windows_rejected_preprocessing": rejected_total,
            "windows_inferred": inferred_total,
            "pipeline_coverage": inferred_total / selected_total if selected_total else 0.0,
            "minimum_session_pipeline_coverage": min(coverages) if coverages else 0.0,
            "sessions": len(per_session),
            "session_ids_excluded": True,
        })
    return data


def rates(rows, threshold):
    known = [r for r in rows if r[0] != "UNKNOWN"]
    unknown = [r for r in rows if r[0] == "UNKNOWN"]
    if not known or not unknown:
        raise ValueError("Both known and UNKNOWN observations are required")
    def accepted(r):
        return r[1] != "UNKNOWN" and r[2] >= threshold
    def macro(part, event):
        sessions = {}
        for item in part:
            sessions.setdefault(item[3], []).append(item)
        return sum(sum(event(x) for x in group) / len(group)
                   for group in sessions.values()) / len(sessions)
    return {
        "threshold": threshold,
        "known_correct_coverage": sum(accepted(r) and r[0] == r[1] for r in known) / len(known),
        "known_wrong_accept_rate": sum(accepted(r) and r[0] != r[1] for r in known) / len(known),
        "unknown_false_accept_rate": sum(accepted(r) for r in unknown) / len(unknown),
        "known_session_macro_coverage":
            macro(known, lambda r: accepted(r) and r[0] == r[1]),
        "unknown_session_macro_false_accept":
            macro(unknown, accepted),
        "known_windows": len(known),
        "unknown_windows": len(unknown),
        "known_sessions": len({r[3] for r in known}),
        "unknown_sessions": len({r[3] for r in unknown}),
    }


def acceptable(r, max_far, min_coverage):
    return (max(r["unknown_false_accept_rate"],
                r["unknown_session_macro_false_accept"]) <= max_far
            and r["known_session_macro_coverage"] >= min_coverage)


def select(rows, max_far=.10, min_coverage=.50):
    if (not math.isfinite(max_far) or not 0 <= max_far <= 1 or
        not math.isfinite(min_coverage) or not 0 <= min_coverage <= 1):
        raise ValueError("Invalid limits")
    curve = [rates(rows, t) for t in THRESHOLDS]
    passing = [r for r in curve if acceptable(r, max_far, min_coverage)]
    best = max(passing, key=lambda r: (
        r["known_session_macro_coverage"],
        r["known_correct_coverage"],
        -r["threshold"])) if passing else None
    return best, curve


def run(cal_manifest, hold_manifest, root, model, max_windows=100,
        max_far=.10, min_coverage=.50, min_pipeline_coverage=.80):
    if not math.isfinite(min_pipeline_coverage) or not 0 <= min_pipeline_coverage <= 1:
        raise ValueError("Invalid minimum pipeline coverage")
    cal, hold = audit(cal_manifest, hold_manifest, root)
    calibration_accounting = {}
    best, curve = select(observations(cal, model, max_windows,
                                      accounting=calibration_accounting),
                         max_far, min_coverage)
    holdout_sessions = len({r[2] for r in hold})
    holdout_devices = len({r[3] for r in hold})
    # An empirical pass on one device or too few sessions is not an
    # independent-device holdout, even when its observed rates look perfect.
    diversity_ok = holdout_sessions >= 3 and holdout_devices >= 2
    result = {
        "scope": "Offline split-session diagnostic; RF authenticity not established",
        "decision": "NO_ACCEPTABLE_THRESHOLD" if best is None else "HOLDOUT_EVALUATED",
        "selected_threshold": best["threshold"] if best else None,
        "calibration_curve": curve,
        "holdout_result": None,
        "calibration_pipeline": calibration_accounting,
        "holdout_pipeline": None,
        "min_pipeline_coverage": min_pipeline_coverage,
        "calibration_sessions": len({r[2] for r in cal}),
        "holdout_sessions": holdout_sessions,
        "distinct_holdout_devices": holdout_devices,
        "min_holdout_sessions": 3,
        "min_distinct_holdout_devices": 2,
        "holdout_diversity_gate_passed": diversity_ok,
        "max_unknown_false_accept": max_far,
        "min_known_correct_coverage": min_coverage,
        "operationally_validated": False,
        "limitations": ("Windows of the same session are correlated. Session-macro rates "
                        "are descriptive, not confidence intervals. True RF provenance, "
                        "labels and out-of-device validation require external evidence."),
    }
    if best:
        holdout_accounting = {}
        holdout = rates(observations(hold, model, max_windows,
                                     accounting=holdout_accounting), best["threshold"])
        result["holdout_result"] = holdout
        result["holdout_pipeline"] = holdout_accounting
        if not acceptable(holdout, max_far, min_coverage):
            result["decision"] = "HOLDOUT_FAILED"
        elif not diversity_ok:
            result["decision"] = "HOLDOUT_INSUFFICIENT_DIVERSITY"
        elif min(calibration_accounting["minimum_session_pipeline_coverage"],
                 holdout_accounting["minimum_session_pipeline_coverage"]) < min_pipeline_coverage:
            result["decision"] = "HOLDOUT_INSUFFICIENT_PIPELINE_COVERAGE"
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--calibration-manifest", type=Path, required=True)
    p.add_argument("--holdout-manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-unknown-far", type=float, default=.10)
    p.add_argument("--min-known-coverage", type=float, default=.50)
    p.add_argument("--max-windows", type=int, default=100)
    p.add_argument("--min-pipeline-coverage", type=float, default=.80,
                   help="Minimum inferred/selected fraction for each session in both splits")
    a = p.parse_args()
    result = run(a.calibration_manifest, a.holdout_manifest, a.root,
                 IQClassifier(a.model), a.max_windows,
                 a.max_unknown_far, a.min_known_coverage, a.min_pipeline_coverage)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Experimental IQ gate:", result["decision"], result["selected_threshold"])
    if result["decision"] != "HOLDOUT_EVALUATED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
