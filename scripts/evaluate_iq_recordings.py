"""Offline evaluation of operator-labeled, channelized IQ WAV recordings.

Never uploads samples or labels. Inputs MUST be stereo PCM16, 48 kS/s,
I=left and Q=right, already centered on the desired signal. WFM unsupported.
"""
import argparse
import json
import math
import wave
from collections import defaultdict
from pathlib import Path
import numpy as np
from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier, SAMPLES

SUPPORTED = tuple(c for c in CLASSES if c != "WFM")

def session_bootstrap_accuracy(session_counts, *, resamples=2000, seed=20261110):
    """Percentile CI from resampled *sessions*, never independent IQ windows.

    Exploratory uncertainty only. An interval is withheld if fewer than
    three independent sessions are available; label verification is external.
    """
    if resamples < 1:
        raise ValueError("resamples must be positive")
    rates = np.array([correct / count for count, correct in session_counts
                      if count > 0], dtype=np.float64)
    if len(rates) < 3:
        return None
    rng = np.random.default_rng(seed)
    samples = rng.choice(rates, size=(resamples, len(rates)), replace=True).mean(axis=1)
    low, high = np.quantile(samples, [0.025, 0.975])
    return {"lower": float(low), "upper": float(high),
            "resamples": resamples, "independent_sessions": len(rates),
            "method": "percentile cluster bootstrap; session macro accuracy",
            "caution": "Exploratory; small sessions or biased sessions cannot validate RF"}


def read_manifest(path: Path, root: Path) -> list:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("recordings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest needs a nonempty recordings array")
    result = []
    seen_files = set()
    session_devices = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Expected a recording object")
        for key in ("path", "session_id", "device", "frequency_hz", "mode"):
            if not row.get(key):
                raise ValueError(f"Missing required recording key: {key}")
        if row["mode"] not in SUPPORTED:
            raise ValueError("Unsupported label; WFM not evaluated by 48k IQ model")
        relative = Path(str(row["path"]))
        if relative.is_absolute():
            raise ValueError("Absolute paths are not allowed")
        source = (root / relative).resolve()
        if not source.is_relative_to(root.resolve()):
            raise ValueError("WAV path leaves recordings root")
        if source in seen_files:
            raise ValueError("Duplicate WAV in manifest: recording cannot be counted twice")
        seen_files.add(source)
        session_id = str(row["session_id"]).strip()
        device_name = str(row["device"]).strip()
        if not session_id or not device_name:
            raise ValueError("session_id and device must be nonempty")
        if session_id in session_devices and session_devices[session_id] != device_name:
            raise ValueError("A session_id cannot span different SDR devices")
        session_devices[session_id] = device_name
        if not source.is_file() or source.suffix.lower() != ".wav":
            raise ValueError("WAV file not found")
        if source.stat().st_size > 512 * 1024 * 1024:
            raise ValueError("WAV exceeds 512 MiB cap")
        if not math.isfinite(float(row["frequency_hz"])) or float(row["frequency_hz"]) <= 0:
            raise ValueError("Invalid frequency")
        result.append((source, row["mode"], session_id, device_name))
    return result


def read_windows(path: Path, limit=100, stats=None, *, with_index=False):
    """Select non-overlapping IQ windows uniformly across the full WAV duration.

    Selecting only the first `limit` windows biases long RF sessions toward
    their startup conditions. The bounded, deterministic selection below
    includes the beginning and end without reading the full file into RAM.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) != (2, 2, 48000, "NONE"):
            raise ValueError("Expected stereo PCM16 48000 Hz IQ WAV")
        total = w.getnframes() // SAMPLES
        # A one-window budget must inspect the middle, not the startup.
        # With >=2 windows, retain deterministic coverage of both edges.
        count = min(limit, total)
        selected = (np.array([(total - 1) // 2], dtype=np.int64)
                    if count == 1 else
                    np.linspace(0, total - 1, count, dtype=np.int64))
        if stats is not None:
            stats["selected"] = stats.get("selected", 0) + len(selected)
        for index in selected:
            w.setpos(int(index) * SAMPLES)
            raw = np.frombuffer(w.readframes(SAMPLES), dtype="<i2")
            if raw.size != 2*SAMPLES:
                break
            iq = (raw[::2].astype(np.float32) + 1j*raw[1::2].astype(np.float32))/32768
            if float(np.sqrt(np.mean(np.abs(iq)**2))) >= 1e-6:
                sample = iq.astype(np.complex64)
                yield (int(index), sample) if with_index else sample
            elif stats is not None:
                stats["skipped_silence"] = stats.get("skipped_silence", 0) + 1


def evaluate(manifest: Path, root: Path, model, max_windows=100,
             *, _inferred_window_ids=None):
    """Keep preprocessing exclusions separate from neural UNKNOWN decisions.

    Model metrics are conditional on inference. Rejected/silent windows never
    enter the neural confusion matrix or count as correct UNKNOWN predictions.
    """
    rows = read_manifest(manifest, root)
    confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=int)
    sessions = defaultdict(lambda: [0, 0])  # inferred, correct
    session_pipeline = defaultdict(lambda: [0, 0])  # selected, inferred
    devices = set()
    confidence_errors = 0
    acceptance = {str(t): {"known_correct": 0, "known_wrong": 0,
                           "known_accepted": 0, "unknown_misaccepted": 0}
                  for t in (0.8, 0.95, 0.99)}
    known_total = 0
    unknown_total = 0
    selected_total = 0
    silent_total = 0
    rejected_total = 0
    rejected_known = 0
    rejected_unknown = 0
    for recording_index, (path, label, session, device) in enumerate(rows):
        devices.add(device)
        session_pipeline[session]  # retain sessions without inferred windows
        stats = {"selected": 0, "skipped_silence": 0}
        for window_index, iq in read_windows(path, max_windows, stats=stats,
                                             with_index=True):
            try:
                result = model.predict(iq)
            except ValueError as exc:
                # Only the explicit DC/unresolved-carrier preprocessing guard
                # is a counted rejection. Other model errors must surface.
                if str(exc) != "No usable RF signal (DC-only or unresolved carrier)":
                    raise
                rejected_total += 1
                if label == "UNKNOWN":
                    rejected_unknown += 1
                else:
                    rejected_known += 1
                continue
            # Exact inferred-window membership is private; equal aggregate counts
            # can hide different model-specific preprocessing exclusions.
            if _inferred_window_ids is not None:
                _inferred_window_ids.add((recording_index, window_index))
            # Validate the complete softmax contract before reporting RF metrics.
            # Malformed probabilities must not create a fictitiously low UNKNOWN FAR.
            probabilities = result.probabilities
            if not isinstance(probabilities, dict) or set(probabilities) != set(CLASSES):
                raise ValueError("Invalid model probability labels")
            if any(isinstance(v, (bool, str)) or
                   not isinstance(v, (int, float, np.integer, np.floating))
                   for v in probabilities.values()):
                raise ValueError("Invalid model probability values")
            scores = {label_name: float(value)
                      for label_name, value in probabilities.items()}
            if (not all(math.isfinite(v) and 0 <= v <= 1 for v in scores.values())
                    or not math.isclose(sum(scores.values()), 1.0,
                                        rel_tol=0.0, abs_tol=1e-4)):
                raise ValueError("Invalid model probabilities: expected normalized softmax")
            if (isinstance(result.confidence, (bool, str))
                    or not isinstance(result.confidence, (int, float, np.integer, np.floating))
                    or not math.isfinite(float(result.confidence))
                    or not 0 <= float(result.confidence) <= 1):
                raise ValueError("Invalid model confidence")
            # Effective mode may be UNKNOWN due to the classifier's configured
            # gate. A threshold sweep must use the raw maximum softmax score,
            # never a separately supplied/stale confidence field.
            top_label = max(scores, key=scores.get)
            top_score = scores[top_label]
            predicted = result.mode
            if predicted not in CLASSES:
                raise ValueError("Invalid classifier mode")
            # A known mode must agree with the raw softmax argmax.
            # UNKNOWN may also be an intentional confidence-gate decision.
            # Otherwise the confusion matrix and the threshold sweep would
            # describe contradictory predictions from the same window.
            if predicted != "UNKNOWN" and predicted != top_label:
                raise ValueError("Classifier mode disagrees with softmax argmax")
            # IQClassifier exposes its configured confidence gate. When it is
            # available, validate BOTH directions: a known class below the
            # gate and UNKNOWN above the gate are inconsistent with predict().
            # Older external stubs without this attribute remain supported.
            gate = getattr(model, "min_confidence", None)
            if gate is not None:
                if (isinstance(gate, (bool, str)) or
                        not isinstance(gate, (int, float, np.integer, np.floating)) or
                        not math.isfinite(float(gate)) or
                        not 0 <= float(gate) <= 1):
                    raise ValueError("Invalid classifier confidence threshold")
                expected_mode = top_label if top_score >= float(gate) else "UNKNOWN"
                if predicted != expected_mode:
                    raise ValueError("Classifier mode disagrees with configured confidence gate")
            confusion[CLASSES.index(label), CLASSES.index(predicted)] += 1
            sessions[session][0] += 1
            sessions[session][1] += int(predicted == label)
            session_pipeline[session][1] += 1
            confidence_errors += int(predicted != label and top_score >= .80)
            if label == "UNKNOWN":
                unknown_total += 1
            else:
                known_total += 1
            for threshold, counts in acceptance.items():
                accepted = top_label != "UNKNOWN" and top_score >= float(threshold)
                if label == "UNKNOWN":
                    counts["unknown_misaccepted"] += int(accepted)
                else:
                    counts["known_accepted"] += int(accepted)
                    counts["known_correct"] += int(accepted and top_label == label)
                    counts["known_wrong"] += int(accepted and top_label != label)
        selected_total += stats["selected"]
        silent_total += stats["skipped_silence"]
        session_pipeline[session][0] += stats["selected"]
    total = int(confusion.sum())
    if total + silent_total + rejected_total != selected_total:
        raise AssertionError("IQ window accounting mismatch")
    session_rates = [correct / count for count, correct in sessions.values()
                     if count]
    coverage_rates = [inferred / selected for selected, inferred in session_pipeline.values()
                      if selected]
    return {
        "scope": "Offline operator-labeled WAV IQ; provenance must be verified",
        "metrics_population": "Neural metrics condition on inferred windows only; preprocessing rejections are not UNKNOWN predictions",
        "sample_windows": total, "windows_selected": selected_total,
        "windows_skipped_silence": silent_total,
        "windows_rejected_preprocessing": rejected_total,
        "windows_rejected_preprocessing_known": rejected_known,
        "windows_rejected_preprocessing_unknown": rejected_unknown,
        "windows_inferred": total,
        "pipeline_coverage": (total / selected_total if selected_total else None),
        "sessions": len(session_pipeline), "devices": len(devices),
        "recordings": len(rows),
        "accuracy_top1": (float(np.trace(confusion) / total) if total else None),
        "high_confidence_error_rate": (float(confidence_errors / total) if total else None),
        "known_windows": known_total, "unknown_windows": unknown_total,
        "acceptance_curve": {
            threshold: {
                "correct_known_accepted_rate": (v["known_correct"] / known_total
                                                if known_total else None),
                "wrong_known_accepted_rate": (v["known_wrong"] / known_total
                                              if known_total else None),
                "known_coverage": (v["known_accepted"] / known_total
                                   if known_total else None),
                "unknown_false_accept_rate": (v["unknown_misaccepted"] / unknown_total
                                              if unknown_total else None),
            } for threshold, v in acceptance.items()
        },
        "per_class_recall": {label: float(confusion[i, i] / confusion[i].sum())
                             if confusion[i].sum() else None
                             for i, label in enumerate(CLASSES)},
        "session_macro_accuracy": (float(np.mean(session_rates))
                                   if session_rates else None),
        "session_macro_accuracy_ci95": session_bootstrap_accuracy(list(sessions.values())),
        "session_accuracy_summary": {
            "min": (float(min(session_rates)) if session_rates else None),
            "max": (float(max(session_rates)) if session_rates else None),
            "sessions": len(session_rates),
            "sessions_without_inference": len(session_pipeline) - len(session_rates),
            "session_ids_excluded": True,
        },
        "session_pipeline_coverage_summary": {
            "min": (float(min(coverage_rates)) if coverage_rates else None),
            "max": (float(max(coverage_rates)) if coverage_rates else None),
            "sessions_with_selected_windows": len(coverage_rates),
            "session_ids_excluded": True,
        },
        "confusion_matrix": confusion.tolist(),
        "limitations": "WFM excluded; model scores exclude silence/DC rejected before inference; windows within a session correlated; cluster-bootstrap CI exploratory only; no automatic RF validation",
    }


def evaluate_multiple_models(manifest: Path, root: Path, models: dict[str, object],
                             max_windows: int = 100) -> dict:
    """Compare models on the same local IQ WAV windows, sessions and metadata."""
    if not models:
        raise ValueError("At least one model is required")
    reports = {}
    inferred_membership = {}
    for alias, model in models.items():
        membership = set()
        reports[alias] = evaluate(manifest, root, model, max_windows,
                                  _inferred_window_ids=membership)
        inferred_membership[alias] = membership
    first_alias = next(iter(reports))
    first = reports[first_alias]
    for alias, report in reports.items():
        for key in ("sample_windows", "sessions", "devices", "recordings",
                    "known_windows", "unknown_windows", "windows_selected",
                    "windows_skipped_silence", "windows_rejected_preprocessing",
                    "windows_rejected_preprocessing_known",
                    "windows_rejected_preprocessing_unknown"):
            if report[key] != first[key]:
                raise ValueError(f"Model {alias} did not process the same dataset")
        if inferred_membership[alias] != inferred_membership[first_alias]:
            raise ValueError(f"Model {alias} did not infer the same IQ windows")
    return {
        "scope": "Local offline comparison on identical operator-labeled IQ WAV windows",
        "models": reports,
        "limitations": "Operator labels and source authenticity must be independently verified",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--additional-model", action="append", default=[],
                   metavar="ALIAS=ONNX", help="Additional ONNX model on the same IQ recordings")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-windows",type=int,default=100)
    a=p.parse_args()
    if a.additional_model:
        models = {"base": IQClassifier(a.model)}
        for item in a.additional_model:
            alias, sep, model_path = item.partition("=")
            if not sep or not alias or not model_path or alias in models:
                raise ValueError("Use unique ALIAS=ONNX for --additional-model")
            models[alias] = IQClassifier(Path(model_path))
        report = evaluate_multiple_models(a.manifest, a.root, models, a.max_windows)
    else:
        report = evaluate(a.manifest, a.root, IQClassifier(a.model), a.max_windows)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    first = next(iter(report["models"].values())) if "models" in report else report
    print("Operator-labelled IQ evaluation:",first["sessions"],"sessions,",first["sample_windows"],"windows")
    if first["sessions"]<3 or first["devices"]<2:
        print("NOT HOMOLOGATED: collect at least three sessions and two different SDRs")


if __name__=="__main__":
    main()
