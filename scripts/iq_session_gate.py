"""Research-only IQ/ONNX threshold selection with disjoint capture sessions.

Do not treat windows from a single capture as independent RF measurements.
No automatic receiver tuning or production promotion is authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from numbers import Real
import wave
from pathlib import Path

from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier
from scripts.evaluate_iq_recordings import read_manifest, read_windows

THRESHOLDS = (0.80, 0.90, 0.95, 0.99, 0.999)
# WFM is explicitly out of scope for the 48 kS/s RF validation contract.
REQUIRED_KNOWN_CLASSES = tuple(c for c in CLASSES if c not in ("UNKNOWN", "WFM"))


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def sampled_iq_window_hashes(path: Path, edge_windows: int = 16) -> set[bytes]:
    """Sample edge, quarter, middle and three-quarter IQ windows for leakage.

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
        # Cover quarter positions too: a copied excerpt at 25% or 75%
        # otherwise escapes the previous first/middle/last-only audit.
        # Each anchor scans at most edge_windows complete IQ windows.
        span = max(0, count - edge_windows)
        starts = (0, span // 4, span // 2, 3 * span // 4, span)
        indices = sorted({index for start in starts
                          for index in range(start, min(count, start + edge_windows))})
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
    # Different paths and session IDs do not establish independent captures.
    # Exact WAV copies inside a split can double-weight one RF event, inflating
    # coverage or diluting OOD false accepts without adding new evidence.
    cal_digests = [digest(row[0]) for row in cal]
    hold_digests = [digest(row[0]) for row in hold]
    if len(set(cal_digests)) != len(cal_digests):
        raise ValueError("Duplicate WAV content within calibration split")
    if len(set(hold_digests)) != len(hold_digests):
        raise ValueError("Duplicate WAV content within holdout split")
    if set(cal_digests) & set(hold_digests):
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
        # Session-macro rates assume known and UNKNOWN captures come from
        # distinct sessions. Two session IDs are not enough when a single
        # session contributes to both populations (pseudo-independence).
        session_families = {}
        for _source, mode, session, _device in rows:
            family = "UNKNOWN" if mode == "UNKNOWN" else "KNOWN"
            if session in session_families and session_families[session] != family:
                raise ValueError(label + " session mixes known and UNKNOWN labels")
            session_families[session] = family
        modes = {r[1] for r in rows}
        if len(session_families) < 2 or "UNKNOWN" not in modes or len(modes) == 1:
            raise ValueError(label + " requires separate known and UNKNOWN sessions")
    return cal, hold


def observations(rows, model, max_windows, *, accounting=None):
    if max_windows < 1:
        raise ValueError("max_windows must be positive")
    data = []
    selected_total = silent_total = rejected_total = inferred_total = 0
    per_session = {}
    per_device_session = {}
    per_recording_coverage = []
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
            probabilities = result.probabilities
            if not isinstance(probabilities, dict) or set(probabilities) != set(CLASSES):
                raise ValueError("Model label mismatch")
            # Do not silently coerce booleans or numeric strings to softmax
            # probabilities. A malformed model must never pass the RF/OOD gate.
            if any(isinstance(value, bool) or not isinstance(value, Real)
                   for value in probabilities.values()):
                raise ValueError("Invalid model probability values")
            scores = {name: float(value) for name, value in probabilities.items()}
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in scores.values()):
                raise ValueError("Invalid model probability")
            # UNKNOWN threshold selection assumes a normalized softmax.
            # Reject malformed model outputs rather than calibrating on them.
            if not math.isclose(sum(scores.values()), 1.0,
                                rel_tol=0.0, abs_tol=1e-4):
                raise ValueError("Model probabilities are not normalized")
            predicted = max(scores, key=scores.get)
            top_score = scores[predicted]
            # Threshold selection uses raw softmax, but it must not certify a
            # classifier whose reported confidence or effective mode contradicts
            # those probabilities. The offline RF evaluator enforces the same
            # contract; the session-based calibration/holdout gate must too.
            confidence = result.confidence
            if (isinstance(confidence, (bool, str))
                    or not isinstance(confidence, Real)
                    or not math.isfinite(float(confidence))
                    or not 0 <= float(confidence) <= 1):
                raise ValueError("Invalid model confidence")
            if not math.isclose(float(confidence), top_score,
                                rel_tol=0.0, abs_tol=1e-6):
                raise ValueError("Classifier confidence disagrees with softmax maximum")
            mode = result.mode
            if not isinstance(mode, str) or mode not in CLASSES:
                raise ValueError("Invalid classifier mode")
            if mode != "UNKNOWN" and mode != predicted:
                raise ValueError("Classifier mode disagrees with softmax argmax")
            gate = getattr(model, "min_confidence", None)
            if gate is not None:
                if (isinstance(gate, (bool, str))
                        or not isinstance(gate, Real)
                        or not math.isfinite(float(gate))
                        or not 0 <= float(gate) <= 1):
                    raise ValueError("Invalid classifier confidence threshold")
                expected_mode = predicted if top_score >= float(gate) else "UNKNOWN"
                if mode != expected_mode:
                    raise ValueError("Classifier mode disagrees with configured confidence gate")
            data.append((label, predicted, top_score, session, _device))
            found += 1
        selected_total += stats["selected"]
        silent_total += stats["skipped_silence"]
        inferred_total += found
        # Two WAVs from one SDR/session can conceal a nearly unusable
        # capture behind a much longer clean recording. Keep each recording
        # as an independent minimum-coverage stratum, without exposing paths.
        per_recording_coverage.append(found / stats["selected"] if stats["selected"] else 0.0)
        session_counts = per_session.setdefault(session, [0, 0])
        session_counts[0] += stats["selected"]
        session_counts[1] += found
        cell_counts = per_device_session.setdefault((session, _device), [0, 0])
        cell_counts[0] += stats["selected"]
        cell_counts[1] += found
        if not found:
            raise ValueError("No inferred IQ windows in recording (silence/DC rejection)")
    if selected_total != silent_total + rejected_total + inferred_total:
        raise AssertionError("IQ gate window accounting mismatch")
    if accounting is not None:
        coverages = [inferred / selected for selected, inferred in per_session.values()
                     if selected]
        cell_coverages = [inferred / selected
                          for selected, inferred in per_device_session.values()
                          if selected]
        accounting.update({
            "windows_selected": selected_total,
            "windows_skipped_silence": silent_total,
            "windows_rejected_preprocessing": rejected_total,
            "windows_inferred": inferred_total,
            "pipeline_coverage": inferred_total / selected_total if selected_total else 0.0,
            "minimum_session_pipeline_coverage": min(coverages) if coverages else 0.0,
            "minimum_device_session_pipeline_coverage": (
                min(cell_coverages) if cell_coverages else 0.0),
            "device_session_cells": len(per_device_session),
            "minimum_recording_pipeline_coverage": min(per_recording_coverage) if per_recording_coverage else 0.0,
            "recordings": len(per_recording_coverage),
            "sessions": len(per_session),
            "session_ids_excluded": True,
        })
    return data


def rates(rows, threshold):
    # Defense in depth: callers of this public helper (including standalone
    # RF threshold tools) must not turn malformed observations into favorable
    # UNKNOWN false-accept rates. In particular NaN >= threshold is False.
    if (isinstance(threshold, bool) or not isinstance(threshold, Real)
            or not math.isfinite(threshold) or not 0 <= threshold <= 1):
        raise ValueError("Invalid IQ decision threshold")
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) not in (4, 5):
            raise ValueError("Expected four or five IQ observation fields")
        label, predicted, confidence, session = row[:4]
        if not isinstance(label, str) or label not in (*REQUIRED_KNOWN_CLASSES, "UNKNOWN"):
            raise ValueError("Invalid IQ reference label")
        if not isinstance(predicted, str) or predicted not in CLASSES:
            raise ValueError("Invalid IQ predicted label")
        if (isinstance(confidence, bool) or not isinstance(confidence, Real)
                or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError("Invalid IQ observation confidence")
        if not isinstance(session, str) or not session.strip():
            raise ValueError("Invalid IQ session identifier")
        if len(row) == 5 and (not isinstance(row[4], str) or not row[4].strip()):
            raise ValueError("Invalid IQ device identifier")
    known = [r for r in rows if r[0] != "UNKNOWN"]
    unknown = [r for r in rows if r[0] == "UNKNOWN"]
    if not known or not unknown:
        raise ValueError("Both known and UNKNOWN observations are required")
    # Legacy four-field rows are accepted by standalone threshold unit tests.
    # The end-to-end RF gate requires a fifth field: the SDR device identity.
    device_fields = [len(r) == 5 for r in rows]
    if any(device_fields) and not all(device_fields):
        raise ValueError("Inconsistent IQ observation device metadata")
    if any(len(r) not in (4, 5) for r in rows):
        raise ValueError("Expected four or five IQ observation fields")
    has_devices = all(device_fields)
    def accepted(r):
        return r[1] != "UNKNOWN" and r[2] >= threshold
    def device_rates(part, event):
        groups = {}
        for item in part:
            groups.setdefault(item[4], []).append(item)
        return [sum(event(x) for x in group) / len(group)
                for group in groups.values()]
    known_device_coverage = (
        device_rates(known, lambda r: accepted(r) and r[0] == r[1])
        if has_devices else None)
    unknown_device_far = (
        device_rates(unknown, accepted) if has_devices else None)
    # A bad UNKNOWN capture on one SDR can be hidden when a session ID is
    # shared by multiple SDRs AND that SDR has other clean sessions. Neither
    # the worst per-session nor worst per-device marginal rate catches it.
    unknown_device_session_far = None
    if has_devices:
        unknown_cells = {}
        for item in unknown:
            unknown_cells.setdefault((item[4], item[3]), []).append(item)
        unknown_device_session_far = [
            sum(accepted(item) for item in cell) / len(cell)
            for cell in unknown_cells.values()
        ]
    # A class can fail completely on one SDR while class-only and device-only
    # averages both pass (Simpson-like masking). Audit each observed
    # (known class, SDR) cell independently; no device IDs leave the report.
    class_device_coverage = None
    class_device_session_coverage = None
    if has_devices:
        cells = {}
        session_cells = {}
        for item in known:
            cells.setdefault((item[0], item[4]), []).append(item)
            session_cells.setdefault((item[0], item[4], item[3]), []).append(item)
        class_device_coverage = [
            sum(accepted(item) and item[0] == item[1] for item in cell) / len(cell)
            for cell in cells.values()
        ]
        # Window-weighted class x SDR rates can hide one completely failed
        # capture session behind many windows from another session in the
        # same cell. A session is the independent unit, not an IQ window.
        class_device_session_coverage = [
            sum(accepted(item) and item[0] == item[1] for item in cell) / len(cell)
            for cell in session_cells.values()
        ]
    def macro(part, event):
        sessions = {}
        for item in part:
            sessions.setdefault(item[3], []).append(item)
        return sum(sum(event(x) for x in group) / len(group)
                   for group in sessions.values()) / len(sessions)
    # A single UNKNOWN session with 100% false acceptance must not be
    # diluted by many quiet sessions or by a window-weighted SDR aggregate.
    unknown_session_groups = {}
    for item in unknown:
        unknown_session_groups.setdefault(item[3], []).append(item)
    unknown_worst_session_far = max(
        sum(accepted(item) for item in group) / len(group)
        for group in unknown_session_groups.values()
    )
    # Per-class session macro: a large AM/NFM corpus must not conceal
    # zero CW coverage. Missing classes require separate RF QA.
    class_labels = {r[0] for r in known}
    worst_class_session_coverage = min(
        macro([r for r in known if r[0] == label],
              lambda r: accepted(r) and r[0] == r[1])
        for label in class_labels)
    return {
        "threshold": threshold,
        "known_correct_coverage": sum(accepted(r) and r[0] == r[1] for r in known) / len(known),
        "known_wrong_accept_rate": sum(accepted(r) and r[0] != r[1] for r in known) / len(known),
        "unknown_false_accept_rate": sum(accepted(r) for r in unknown) / len(unknown),
        "known_session_macro_coverage":
            macro(known, lambda r: accepted(r) and r[0] == r[1]),
        "known_worst_class_session_macro_coverage": worst_class_session_coverage,
        "known_classes_observed": len(class_labels),
        "unknown_session_macro_false_accept":
            macro(unknown, accepted),
        "unknown_worst_session_false_accept_rate": unknown_worst_session_far,
        # Device-level worst case prevents many sessions from one good SDR
        # masking an OOD failure on a different SDR. Device IDs stay private.
        "known_worst_device_correct_coverage": (
            min(known_device_coverage) if known_device_coverage is not None else None),
        "known_worst_class_device_correct_coverage": (
            min(class_device_coverage) if class_device_coverage is not None else None),
        "known_class_device_cells_observed": (
            len(class_device_coverage) if class_device_coverage is not None else None),
        "known_worst_class_device_session_correct_coverage": (
            min(class_device_session_coverage)
            if class_device_session_coverage is not None else None),
        "known_class_device_session_cells_observed": (
            len(class_device_session_coverage)
            if class_device_session_coverage is not None else None),
        "unknown_worst_device_false_accept_rate": (
            max(unknown_device_far) if unknown_device_far is not None else None),
        "unknown_worst_device_session_false_accept_rate": (
            max(unknown_device_session_far)
            if unknown_device_session_far is not None else None),
        "unknown_device_session_cells_observed": (
            len(unknown_device_session_far)
            if unknown_device_session_far is not None else None),
        "known_devices": len(known_device_coverage) if has_devices else None,
        "unknown_devices": len(unknown_device_far) if has_devices else None,
        "device_ids_excluded": True,
        "known_windows": len(known),
        "unknown_windows": len(unknown),
        "known_sessions": len({r[3] for r in known}),
        "unknown_sessions": len({r[3] for r in unknown}),
    }


def acceptable(r, max_far, min_coverage):
    return (max(r["unknown_false_accept_rate"],
                r["unknown_session_macro_false_accept"],
                r["unknown_worst_session_false_accept_rate"],
                r["unknown_worst_device_false_accept_rate"] or 0.0,
                r["unknown_worst_device_session_false_accept_rate"] or 0.0) <= max_far
            and r["known_session_macro_coverage"] >= min_coverage
            and r["known_worst_class_session_macro_coverage"] >= min_coverage
            and (r["known_worst_device_correct_coverage"] is None or
                 r["known_worst_device_correct_coverage"] >= min_coverage)
            and (r["known_worst_class_device_correct_coverage"] is None or
                 r["known_worst_class_device_correct_coverage"] >= min_coverage)
            and (r["known_worst_class_device_session_correct_coverage"] is None or
                 r["known_worst_class_device_session_correct_coverage"] >= min_coverage))


def select(rows, max_far=.10, min_coverage=.50):
    # Boolean flags are integers in Python (True == 1, False == 0).
    # Treating max_far=True or min_coverage=False as numeric limits can
    # silently disable RF/OOD rejection or known-class coverage gates.
    if any(isinstance(value, bool) or not isinstance(value, Real)
           or not math.isfinite(value) or not 0 <= value <= 1
           for value in (max_far, min_coverage)):
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
    if (isinstance(min_pipeline_coverage, bool)
            or not isinstance(min_pipeline_coverage, Real)
            or not math.isfinite(min_pipeline_coverage)
            or not 0 <= min_pipeline_coverage <= 1):
        raise ValueError("Invalid minimum pipeline coverage")
    cal, hold = audit(cal_manifest, hold_manifest, root)
    calibration_accounting = {}
    calibration_observations = observations(
        cal, model, max_windows, accounting=calibration_accounting)
    if any(len(row) != 5 for row in calibration_observations):
        raise ValueError("Device metadata required for IQ calibration gate")
    best, curve = select(calibration_observations, max_far, min_coverage)
    holdout_sessions = len({r[2] for r in hold})
    holdout_devices = len({r[3] for r in hold})
    # Aggregate diversity alone can hide a single UNKNOWN session or a
    # single UNKNOWN device. Window counts do not replace independent RF
    # sessions; require both label populations across independent devices.
    known_rows = [r for r in hold if r[1] != "UNKNOWN"]
    unknown_rows = [r for r in hold if r[1] == "UNKNOWN"]
    holdout_known_sessions = len({r[2] for r in known_rows})
    holdout_unknown_sessions = len({r[2] for r in unknown_rows})
    holdout_known_devices = len({r[3] for r in known_rows})
    holdout_unknown_devices = len({r[3] for r in unknown_rows})
    diversity_ok = (holdout_sessions >= 4 and holdout_devices >= 2
                    and holdout_known_sessions >= 2 and holdout_unknown_sessions >= 2
                    and holdout_known_devices >= 2 and holdout_unknown_devices >= 2)
    # A favorable AM-only holdout cannot be presented as evaluation of CW,
    # NFM, USB or LSB. Check independent manifest labels in BOTH splits.
    required = set(REQUIRED_KNOWN_CLASSES)
    missing_calibration = sorted(required - {r[1] for r in cal})
    missing_holdout = sorted(required - {r[1] for r in hold})
    class_coverage_ok = not (missing_calibration or missing_holdout)
    # Aggregate class coverage and observed class/SDR cells are insufficient:
    # an untested CW/SDR combination cannot count as a successful RF holdout.
    # Require each held-out SDR to contribute every required known mode AND
    # UNKNOWN. Publish counts only, never private SDR identifiers.
    holdout_devices_set = {r[3] for r in hold}
    observed_holdout_cells = {(r[1], r[3]) for r in hold}
    expected_holdout_cells = {
        (mode, device)
        for device in holdout_devices_set
        for mode in (*REQUIRED_KNOWN_CLASSES, "UNKNOWN")
    }
    missing_holdout_cells = expected_holdout_cells - observed_holdout_cells
    class_device_coverage_ok = not missing_holdout_cells
    # A complete class x SDR matrix can still contain only one capture
    # session per cell. Repeated windows or WAVs from that session are not
    # independent evidence. Count unique session IDs, including UNKNOWN.
    holdout_cell_sessions = {}
    for _source, mode, session, device in hold:
        holdout_cell_sessions.setdefault((mode, device), set()).add(session)
    min_sessions_per_cell = 2
    under_sampled_holdout_cells = sum(
        len(holdout_cell_sessions.get(cell, ())) < min_sessions_per_cell
        for cell in expected_holdout_cells)
    class_device_session_diversity_ok = under_sampled_holdout_cells == 0
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
        "holdout_known_sessions": holdout_known_sessions,
        "holdout_unknown_sessions": holdout_unknown_sessions,
        "holdout_known_devices": holdout_known_devices,
        "holdout_unknown_devices": holdout_unknown_devices,
        "min_holdout_sessions": 4,
        "min_holdout_sessions_per_population": 2,
        "min_distinct_holdout_devices": 2,
        "min_distinct_holdout_devices_per_population": 2,
        "holdout_diversity_gate_passed": diversity_ok,
        "required_known_classes": list(REQUIRED_KNOWN_CLASSES),
        "missing_known_classes_calibration": missing_calibration,
        "missing_known_classes_holdout": missing_holdout,
        "holdout_class_coverage_gate_passed": class_coverage_ok,
        "holdout_class_device_coverage_gate_passed": class_device_coverage_ok,
        "required_holdout_class_device_cells": len(expected_holdout_cells),
        "missing_holdout_class_device_cells": len(missing_holdout_cells),
        "min_holdout_sessions_per_class_device_cell": min_sessions_per_cell,
        "holdout_class_device_session_diversity_gate_passed":
            class_device_session_diversity_ok,
        "holdout_class_device_cells_below_min_sessions": under_sampled_holdout_cells,
        "max_unknown_false_accept": max_far,
        "min_known_correct_coverage": min_coverage,
        "operationally_validated": False,
        "limitations": ("Windows of the same session are correlated. Session/device "
                        "worst-case rates are descriptive, not confidence intervals. "
                        "Device names in manifests require external identity verification. "
                        "True RF provenance, labels and out-of-device validation "
                        "require external evidence."),
    }
    if best:
        holdout_accounting = {}
        holdout_observations = observations(
            hold, model, max_windows, accounting=holdout_accounting)
        if any(len(row) != 5 for row in holdout_observations):
            raise ValueError("Device metadata required for IQ holdout gate")
        holdout = rates(holdout_observations, best["threshold"])
        result["holdout_result"] = holdout
        result["holdout_pipeline"] = holdout_accounting
        if not acceptable(holdout, max_far, min_coverage):
            result["decision"] = "HOLDOUT_FAILED"
        elif not diversity_ok:
            result["decision"] = "HOLDOUT_INSUFFICIENT_DIVERSITY"
        elif min(
            calibration_accounting["minimum_session_pipeline_coverage"],
            holdout_accounting["minimum_session_pipeline_coverage"],
            calibration_accounting.get(
                "minimum_device_session_pipeline_coverage",
                calibration_accounting["minimum_session_pipeline_coverage"]),
            holdout_accounting.get(
                "minimum_device_session_pipeline_coverage",
                holdout_accounting["minimum_session_pipeline_coverage"]),
            calibration_accounting.get(
                "minimum_recording_pipeline_coverage",
                calibration_accounting["minimum_session_pipeline_coverage"]),
            holdout_accounting.get(
                "minimum_recording_pipeline_coverage",
                holdout_accounting["minimum_session_pipeline_coverage"]),
        ) < min_pipeline_coverage:
            result["decision"] = "HOLDOUT_INSUFFICIENT_PIPELINE_COVERAGE"
        elif not class_coverage_ok:
            result["decision"] = "HOLDOUT_INSUFFICIENT_CLASS_COVERAGE"
        elif not class_device_coverage_ok:
            result["decision"] = "HOLDOUT_INSUFFICIENT_CLASS_DEVICE_COVERAGE"
        elif not class_device_session_diversity_ok:
            result["decision"] = "HOLDOUT_INSUFFICIENT_CLASS_DEVICE_SESSION_DIVERSITY"
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
