"""Offline evaluation of operator-labeled, channelized IQ WAV recordings.

Never uploads samples or labels. Inputs MUST be stereo PCM16, 48 kS/s,
I=left and Q=right, already centered on the desired signal. WFM unsupported.
"""
import argparse
import json
import wave
from collections import defaultdict
from pathlib import Path
import numpy as np
from pt2vhf.dsp.iq_classifier import CLASSES, IQClassifier, SAMPLES

SUPPORTED = tuple(c for c in CLASSES if c != "WFM")


def read_manifest(path: Path, root: Path) -> list:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("recordings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest needs a nonempty recordings array")
    result = []
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
        if not source.is_file() or source.suffix.lower() != ".wav":
            raise ValueError("WAV file not found")
        if source.stat().st_size > 512 * 1024 * 1024:
            raise ValueError("WAV exceeds 512 MiB cap")
        if float(row["frequency_hz"]) <= 0:
            raise ValueError("Invalid frequency")
        result.append((source, row["mode"], str(row["session_id"]), str(row["device"])))
    return result


def read_windows(path: Path, limit=100):
    """Generate strictly non-overlapping 2048-sample windows."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) != (2, 2, 48000, "NONE"):
            raise ValueError("Expected stereo PCM16 48000 Hz IQ WAV")
        for _ in range(min(limit, w.getnframes() // SAMPLES)):
            raw = np.frombuffer(w.readframes(SAMPLES), dtype="<i2")
            if raw.size != 2*SAMPLES:
                break
            iq = (raw[::2].astype(np.float32) + 1j*raw[1::2].astype(np.float32))/32768
            if float(np.sqrt(np.mean(np.abs(iq)**2))) >= 1e-6:
                yield iq.astype(np.complex64)


def evaluate(manifest: Path, root: Path, model, max_windows=100):
    rows = read_manifest(manifest, root)
    confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=int)
    sessions = defaultdict(lambda: [0, 0])
    devices = set()
    confidence_errors = 0
    for path, label, session, device in rows:
        devices.add(device)
        got = 0
        for iq in read_windows(path, max_windows):
            result = model.predict(iq)
            predicted = max(result.probabilities, key=result.probabilities.get)
            confusion[CLASSES.index(label), CLASSES.index(predicted)] += 1
            sessions[session][0] += 1
            sessions[session][1] += int(predicted == label)
            confidence_errors += int(predicted != label and result.confidence >= .80)
            got += 1
        if not got:
            raise ValueError(f"No usable IQ samples: {path.name}")
    total = int(confusion.sum())
    return {
        "scope": "Offline operator-labeled WAV IQ; provenance must be verified",
        "sample_windows": total, "sessions": len(sessions),
        "devices": len(devices), "recordings": len(rows),
        "accuracy_top1": float(np.trace(confusion)/total),
        "high_confidence_error_rate": float(confidence_errors/total),
        "per_class_recall": {label:float(confusion[i,i]/confusion[i].sum())
                             if confusion[i].sum() else None
                             for i,label in enumerate(CLASSES)},
        "session_macro_accuracy": float(np.mean([correct/count for count,correct in sessions.values()])),
        "confusion_matrix": confusion.tolist(),
        "limitations": "WFM excluded; windows within a session correlated; no automatic RF validation",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-windows",type=int,default=100)
    a=p.parse_args()
    report=evaluate(a.manifest,a.root,IQClassifier(a.model),a.max_windows)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("RF-labelled candidate evaluation:",report["sessions"],"sessions,",report["sample_windows"],"windows")
    if report["sessions"]<3 or report["devices"]<2:
        print("NOT HOMOLOGATED: collect at least three sessions and two different SDRs")


if __name__=="__main__":
    main()
