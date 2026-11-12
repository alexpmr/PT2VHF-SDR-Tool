"""Optional ONNX IQ signal classifier. Never changes the receiver automatically.

Model contract: float32 [1, 2, 2048] (I/Q), output logits [1, 7].
Class order: CW, AM, NFM, WFM, USB, LSB, UNKNOWN.
An untrained or missing model must NEVER produce fabricated predictions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np

CLASSES = ("CW", "AM", "NFM", "WFM", "USB", "LSB", "UNKNOWN")
SAMPLES = 2048


@dataclass(frozen=True)
class Classification:
    mode: str
    confidence: float
    probabilities: dict[str, float]


class IQClassifier:
    def __init__(self, model_path: str | Path, min_confidence: float = 0.8):
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Trained ONNX model missing: {path}")
        import onnxruntime as ort
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError("Expected one input and one output")
        if list(inputs[0].shape)[1:] != [2, SAMPLES]:
            raise ValueError("Expected input shape [batch, 2, 2048]")
        self.input_name = inputs[0].name
        self.min_confidence = float(np.clip(min_confidence, 0.0, 1.0))

    @staticmethod
    def features(iq) -> np.ndarray:
        samples = np.asarray(iq, dtype=np.complex64).reshape(-1)
        if samples.size < SAMPLES:
            raise ValueError("Insufficient IQ samples")
        if not np.all(np.isfinite(samples)):
            raise ValueError("Non-finite IQ samples")
        # Center crop, DC removal and RMS normalization. A constant
        # complex carrier can leave float32 roundoff after mean subtraction.
        # That residual must NEVER be amplified into apparent RF content.
        start = (samples.size - SAMPLES) // 2
        samples = samples[start:start + SAMPLES].copy()
        original_rms = float(np.sqrt(np.mean(
            np.abs(samples.astype(np.complex128)) ** 2)))
        # Keep the existing float32 path for normal RF amplitudes: the
        # experimental ONNX models were evaluated with that preprocessing.
        # For *finite* but very large IQ, float32 squaring or centering can
        # overflow to inf/NaN, turning valid RF into an all-zero tensor and
        # potentially a fabricated high-confidence prediction. Recompute only
        # that exceptional case in float64, before normalization.
        raw = samples.copy()
        with np.errstate(over="ignore", invalid="ignore"):
            samples -= samples.mean()
            rms = float(np.sqrt(np.mean(np.abs(samples) ** 2)))
        if not np.isfinite(rms):
            centered64 = raw.astype(np.complex128)
            centered64 -= centered64.mean()
            rms = float(np.sqrt(np.mean(np.abs(centered64) ** 2)))
            if not np.isfinite(rms) or rms < max(1e-8, original_rms * 1e-5):
                raise ValueError("No usable RF signal (DC-only or unresolved carrier)")
            centered64 /= rms
            return np.stack((centered64.real, centered64.imag), axis=0)[None].astype(np.float32)
        if rms < max(1e-8, original_rms * 1e-5):
            raise ValueError("No usable RF signal (DC-only or unresolved carrier)")
        samples /= rms
        return np.stack((samples.real, samples.imag), axis=0)[None].astype(np.float32)

    def predict(self, iq) -> Classification:
        logits = np.asarray(self.session.run(None, {self.input_name: self.features(iq)})[0])
        if logits.shape != (1, len(CLASSES)) or not np.all(np.isfinite(logits)):
            raise ValueError("Invalid model output")
        scores = logits[0].astype(np.float64)
        probs = np.exp(scores - scores.max())
        probs /= probs.sum()
        best = int(probs.argmax())
        confidence = float(probs[best])
        mode = CLASSES[best] if confidence >= self.min_confidence else "UNKNOWN"
        return Classification(mode, confidence, dict(zip(CLASSES, map(float, probs))))
