"""Prepare channel-centered 48 kS/s IQ WAV from SDR Tool's raw IQ recordings.

Offline, receive-only. Labels come from the operator, NOT the neural model.
Input: stable-center stereo PCM16 IQ, I=left, Q=right. Process in bounded
chunks with a continuous NCO and FIR state. Never overwrite output recordings.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy.signal import firwin, lfilter
from pt2vhf.iq_provenance import sidecar_path

RATE = 48000
LABELS = ("CW", "AM", "NFM", "USB", "LSB", "UNKNOWN")


def input_info(src: Path):
    with wave.open(str(src), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getcomptype()) != (2, 2, "NONE"):
            raise ValueError("Input must be stereo PCM16 IQ WAV, I=left Q=right")
        fs, frames = w.getframerate(), w.getnframes()
    if not (RATE <= fs <= 3_072_000 and fs % RATE == 0):
        raise ValueError("Source sample rate must be an integer multiple of 48k, up to 3.072MHz")
    if frames // (fs // RATE) < 2048:
        raise ValueError("Recording too short for 2048 IQ output samples")
    return fs, frames


def check_recording_metadata(source: Path, sample_rate: int, frames: int,
                             requested_center: float | None) -> tuple[float, bool]:
    """Reject invalid PT2VHF capture metadata; legacy WAV needs manual center.

    Metadata is unsigned operator information, not trusted proof of RF.
    """
    path = sidecar_path(source)
    if not path.exists():
        if requested_center is None:
            raise ValueError("Missing --center-hz and PT2VHF IQ sidecar")
        return float(requested_center), False
    meta = json.loads(path.read_text(encoding="utf-8"))
    if (meta.get("schema_version") != 1 or
        meta.get("capture_kind") != "pt2vhf_raw_iq" or
        meta.get("wav_name") != source.name or
        meta.get("completed") is not True):
        raise ValueError("Invalid/incomplete IQ recording sidecar")
    if (meta.get("suitable_for_continuous_channelization") is not True or
        meta.get("invalid_reasons") or meta.get("iq_vox") is not False or
        meta.get("center_change_count") != 0 or
        meta.get("sample_rate_change_count") != 0):
        raise ValueError("IQ recording changed frequency/rate or used VOX; cannot channelize safely")
    if (meta.get("sample_rate_hz") != sample_rate or
        meta.get("written_frames") != frames):
        raise ValueError("IQ sidecar sample rate/frame count mismatch")
    center = meta.get("center_hz")
    if not isinstance(center, (int, float)) or not math.isfinite(float(center)) or center <= 0:
        raise ValueError("Invalid center frequency in IQ sidecar")
    if requested_center is not None and abs(float(center) - float(requested_center)) > 0.5:
        raise ValueError("Requested center frequency differs from IQ recording sidecar")
    return float(center), True


def convert(source: Path, dest: Path, center_hz: float | None, target_hz: float, chunk=65536):
    if chunk < 1:
        raise ValueError("chunk must be positive")
    if not math.isfinite(float(target_hz)) or target_hz <= 0:
        raise ValueError("Frequencies must be positive and finite")
    if center_hz is not None and (not math.isfinite(float(center_hz)) or center_hz <= 0):
        raise ValueError("Frequencies must be positive and finite")
    fs, frames = input_info(source)
    center_hz, metadata_checked = check_recording_metadata(source, fs, frames, center_hz)
    ratio = fs // RATE
    delta = float(target_hz) - float(center_hz)
    if abs(delta) >= fs / 2 - RATE / 2:
        raise ValueError("Target too close to Nyquist edge of recorded IQ")
    if dest.exists():
        raise FileExistsError("Output exists; refusing to overwrite IQ")
    if source.resolve() == dest.resolve():
        raise ValueError("Input and output must be different files")
    taps = firwin(24 * ratio + 1, RATE * .45, fs=fs, window=("kaiser", 8.6))
    zi = np.zeros(len(taps)-1, np.complex128)
    delay = (len(taps)-1) // (2*ratio)
    phase = 0
    skip = delay
    consumed = 0
    written = 0
    expected = frames // ratio
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".iq_", suffix=".wav",
                                         dir=dest.parent, delete=False) as handle:
            tmp = Path(handle.name)
        with wave.open(str(source), "rb") as inp, wave.open(str(tmp), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(RATE)
            def feed(samples):
                nonlocal zi, phase, skip, written
                filtered, zi = lfilter(taps, [1.0], samples, zi=zi)
                down = filtered[phase::ratio]
                phase = (phase - len(samples)) % ratio
                if skip:
                    skipped = min(skip, len(down))
                    down = down[skipped:]
                    skip -= skipped
                down = down[:max(0, expected-written)]
                if len(down):
                    inter = np.empty(2 * len(down), dtype="<i2")
                    inter[0::2] = np.clip(np.round(down.real * 32767),-32768,32767).astype("<i2")
                    inter[1::2] = np.clip(np.round(down.imag * 32767),-32768,32767).astype("<i2")
                    out.writeframesraw(inter.tobytes())
                    written += len(down)
            while consumed < frames:
                raw = np.frombuffer(inp.readframes(min(chunk, frames-consumed)), dtype="<i2")
                if len(raw) < 2 or len(raw) % 2:
                    raise ValueError("Truncated WAV IQ samples")
                n = len(raw)//2
                iq = (raw[::2].astype(np.float64) + 1j*raw[1::2].astype(np.float64))/32768
                angles = -2*np.pi*delta*(consumed + np.arange(n))/fs
                feed(iq * np.exp(1j*angles))
                consumed += n
            feed(np.zeros((delay+1)*ratio, np.complex128))
        if written != expected:
            raise RuntimeError("Output IQ frame count did not match continuous decimator")
        # Hard link to avoid accidentally overwriting a file created concurrently.
        os.link(tmp, dest)
        return {"input_rate":fs, "output_rate":RATE, "frames":written,
                "center_hz":center_hz, "target_hz":target_hz,
                "capture_metadata_checked":metadata_checked,
                "provenance_verified":False}
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def append_manifest(path: Path, root: Path, output: Path, mode: str,
                    session: str, device: str, target_hz: float):
    if mode not in LABELS:
        raise ValueError("WFM/invalid class is unsupported")
    if not session.strip() or not device.strip():
        raise ValueError("Session and device cannot be empty")
    root = root.resolve()
    output = output.resolve()
    if not output.is_relative_to(root):
        raise ValueError("Output WAV is outside recordings root")
    manifest = json.loads(path.read_text(encoding="utf8")) if path.exists() else {"recordings":[]}
    rows = manifest.get("recordings")
    if not isinstance(rows, list):
        raise ValueError("Invalid manifest recordings array")
    relative = output.relative_to(root).as_posix()
    if any(x.get("path") == relative for x in rows):
        raise ValueError("Recording already listed in manifest")
    if any(x.get("session_id")==session and x.get("device")!=device for x in rows):
        raise ValueError("One session cannot mix different devices")
    rows.append({"path":relative, "mode":mode, "session_id":session,
                 "device":device, "frequency_hz":float(target_hz)})
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("x", encoding="utf8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description="Convert broadband IQ WAV to 48k channel IQ for ONNX tests")
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--center-hz",type=float,
                   help="Required for legacy WAV; optional when valid .iq.json sidecar exists")
    p.add_argument("--target-hz",type=float,required=True)
    p.add_argument("--mode",choices=LABELS,required=True)
    p.add_argument("--device",required=True)
    p.add_argument("--session",required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    args=p.parse_args()
    if not args.output.resolve().is_relative_to(args.root.resolve()):
        p.error("Output must be inside recordings root")
    if not args.manifest.resolve().is_relative_to(args.root.resolve()):
        p.error("Manifest must be inside recordings root")
    result=convert(args.input,args.output,args.center_hz,args.target_hz)
    append_manifest(args.manifest,args.root,args.output,args.mode,args.session,
                    args.device,args.target_hz)
    print(json.dumps({"result":result, "manifest":str(args.manifest),
                      "warning":"Operator's RF label/provenance not verified"},indent=2))


if __name__=="__main__":
    main()
