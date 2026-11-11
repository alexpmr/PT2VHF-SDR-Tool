"""End-to-end ONNX + WAV reader smoke test with SYNTHETIC data only.

No real RF data, no field-performance assertions. This checks that all
exported ONNX models consume the same IQ WAV samples without crashes.
"""
from __future__ import annotations

import json
import tempfile
import wave
from pathlib import Path

import numpy as np

from pt2vhf.dsp.iq_classifier import IQClassifier
from scripts.evaluate_iq_recordings import evaluate_multiple_models
from scripts.iq_out_of_family import sample


def run(model_paths: dict[str, Path]) -> dict:
    rng = np.random.default_rng(20261115)
    with tempfile.TemporaryDirectory(prefix="pt2vhf_iq_smoke_") as directory:
        root = Path(directory)
        records = []
        for mode in ("AM", "NFM", "UNKNOWN"):
            iq = np.concatenate([sample(mode, rng, 12) for _ in range(4)])
            pcm = np.empty((len(iq), 2), dtype="<i2")
            pcm[:, 0] = np.clip(np.round(iq.real * 12000), -32768, 32767).astype("<i2")
            pcm[:, 1] = np.clip(np.round(iq.imag * 12000), -32768, 32767).astype("<i2")
            name = mode.lower() + ".wav"
            with wave.open(str(root / name), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(48000)
                wav.writeframes(pcm.tobytes())
            records.append({
                "path": name, "mode": mode,
                "session_id": "synthetic-" + mode,
                "device": "SYNTHETIC ONLY",
                "frequency_hz": 145500000,
            })
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"recordings": records}), encoding="utf-8")
        models = {name: IQClassifier(path) for name, path in model_paths.items()}
        result = evaluate_multiple_models(manifest, root, models)
    for name, metric in result["models"].items():
        assert metric["sample_windows"] == 12
        assert metric["sessions"] == 3
        assert metric["recordings"] == 3
        assert metric["known_windows"] == 8
        assert metric["unknown_windows"] == 4
        assert np.isfinite(metric["accuracy_top1"])
        print(f"{name}: synthetic WAV pipeline pass; "
              f"top1={metric['accuracy_top1']:.3f} "
              f"UNKNOWN falsely accepted={metric['acceptance_curve']['0.8']['unknown_false_accept_rate']:.3f}",
              flush=True)
    return result


def main():
    paths = {v: Path(f"models/iq/synthetic_{v}.onnx") for v in ("v2", "v3", "v4", "v5")}
    result = run(paths)
    output = Path("models/iq/synthetic_wav_smoke_metrics.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "source": "SYNTHETIC WAV ONLY; no actual RF",
        "result": result,
    }, indent=2) + "\n", encoding="utf-8")
    print("WAV/ONNX smoke metrics saved:", output)


if __name__ == "__main__":
    main()
