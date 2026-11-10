"""Prepare channel-centered 48 kS/s IQ WAV from SDR Tool's raw IQ recordings.

Offline, receive-only. Labels come from the operator, NOT the neural model.
Input: stable-center stereo PCM16 IQ, I=left, Q=right. Process in bounded
chunks with a continuous NCO and FIR state. Never overwrite output recordings.
"""
from __future__ import annotations
import argparse
import hmac
import json
import math
import os
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy.signal import firwin, resample_poly
from pt2vhf.iq_provenance import sha256_file, sidecar_path

RATE = 48000
# Keep very uncommon, near-coprime device rates from allocating millions of
# FIR coefficients. Use a supported hardware rate or rational resampling stage.
MAX_RESAMPLE_FACTOR = 4096
LABELS = ("CW", "AM", "NFM", "USB", "LSB", "UNKNOWN")


def input_info(src: Path):
    with wave.open(str(src), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getcomptype()) != (2, 2, "NONE"):
            raise ValueError("Input must be stereo PCM16 IQ WAV, I=left Q=right")
        fs, frames = w.getframerate(), w.getnframes()
    if not (RATE <= fs <= 3_072_000):
        raise ValueError("Source sample rate must be from 48 kS/s to 3.072 MS/s")
    if (frames * RATE + fs - 1) // fs < 2048:
        raise ValueError("Recording too short for 2048 IQ output samples")
    return fs, frames


def check_recording_metadata(source: Path, sample_rate: int, frames: int,
                             requested_center: float | None) -> tuple[float, bool, bool]:
    """Reject invalid PT2VHF capture metadata; legacy WAV needs manual center.

    Metadata is unsigned operator information, not trusted proof of RF.
    """
    path = sidecar_path(source)
    if not path.exists():
        if requested_center is None:
            raise ValueError("Missing --center-hz and PT2VHF IQ sidecar")
        return float(requested_center), False, False
    meta = json.loads(path.read_text(encoding="utf-8"))
    if (meta.get("schema_version") not in (1, 2) or
        meta.get("capture_kind") != "pt2vhf_raw_iq" or
        meta.get("wav_name") != source.name or
        meta.get("completed") is not True):
        raise ValueError("Invalid/incomplete IQ recording sidecar")
    if (meta.get("suitable_for_continuous_channelization") is not True or
        meta.get("invalid_reasons") or meta.get("iq_vox") is not False or
        meta.get("center_change_count") != 0 or
        meta.get("sample_rate_change_count") != 0 or
        meta.get("dropped_iq_blocks_during_capture", 0) != 0 or
        meta.get("source_drop_counter_resets", 0) != 0 or
        meta.get("interruption_reason") is not None):
        raise ValueError("IQ recording has interruptions, dropped blocks, frequency/rate changes or VOX")
    if (meta.get("sample_rate_hz") != sample_rate or
        meta.get("written_frames") != frames):
        raise ValueError("IQ sidecar sample rate/frame count mismatch")
    center = meta.get("center_hz")
    if not isinstance(center, (int, float)) or not math.isfinite(float(center)) or center <= 0:
        raise ValueError("Invalid center frequency in IQ sidecar")
    if requested_center is not None and abs(float(center) - float(requested_center)) > 0.5:
        raise ValueError("Requested center frequency differs from IQ recording sidecar")
    integrity_ok = False
    if meta["schema_version"] == 2:
        checksum = meta.get("wav_sha256")
        if (meta.get("capture_state") != "complete" or
            not isinstance(checksum, str) or len(checksum) != 64 or
            any(ch not in "0123456789abcdef" for ch in checksum)):
            raise ValueError("Incomplete or invalid WAV SHA-256 in IQ sidecar")
        if (type(meta.get("wav_size_bytes")) is not int or
            meta["wav_size_bytes"] != source.stat().st_size):
            raise ValueError("WAV file size differs from IQ sidecar")
        if not hmac.compare_digest(sha256_file(source), checksum):
            raise ValueError("WAV SHA-256 mismatch: recording changed after capture")
        integrity_ok = True
    return float(center), True, integrity_ok



def convert(source: Path, dest: Path, center_hz: float | None, target_hz: float,
            chunk=65536):
    """Channelize IQ to 48 kS/s with state-equivalent polyphase resampling.

    Read bounded chunks from disk. Choose an input block size divisible by the
    rational resampling denominator, plus symmetric FIR guard samples. The
    guard makes boundaries sample-identical to full-file resample_poly.
    """
    if chunk < 1:
        raise ValueError("chunk must be positive")
    if not math.isfinite(float(target_hz)) or target_hz <= 0:
        raise ValueError("Frequencies must be positive and finite")
    if center_hz is not None and (not math.isfinite(float(center_hz)) or center_hz <= 0):
        raise ValueError("Frequencies must be positive and finite")
    fs, frames = input_info(source)
    center_hz, metadata_checked, integrity_verified = check_recording_metadata(
        source, fs, frames, center_hz
    )
    delta = float(target_hz) - float(center_hz)
    # A 48k IQ WAV may already be channelized and needs no guard band if
    # it is NOT frequency-shifted. Any retuning requires a wider capture.
    if abs(delta) >= fs / 2 - RATE / 2 and not (fs == RATE and delta == 0):
        raise ValueError("Target too close to Nyquist edge of recorded IQ")
    if dest.exists():
        raise FileExistsError("Output exists; refusing to overwrite IQ")
    if source.resolve() == dest.resolve():
        raise ValueError("Input and output must be different files")

    divisor = math.gcd(fs, RATE)
    up, down = RATE // divisor, fs // divisor
    if max(up, down) > MAX_RESAMPLE_FACTOR:
        raise ValueError(
            "Unsupported high-complexity IQ resampling ratio; configure a "
            "standard SDR sample rate (e.g. 1.024, 2.048 or 2.4 MS/s)"
        )
    # Kaiser FIR: passband up to ~21.6 kHz and stopband before output Nyquist.
    # Filter taps are defined at the upsampled rate used by resample_poly.
    taps = firwin(20 * max(up, down) + 1, 0.90 / max(up, down),
                  window=("kaiser", 8.6))
    half_width = (len(taps) - 1) // 2
    # Choose a guard that contains the entire half-width of the FIR and is
    # divisible by down. That also makes output sampling phase consistent.
    halo = ((math.ceil(half_width / up) + down - 1) // down) * down
    block_size = ((max(chunk, 2 * halo) + down - 1) // down) * down
    expected = (frames * up + down - 1) // down

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    input_index = 0
    written = 0
    try:
        with tempfile.NamedTemporaryFile(prefix=".iq_", suffix=".wav",
                                         dir=dest.parent, delete=False) as handle:
            tmp = Path(handle.name)
        with wave.open(str(source), "rb") as inp, wave.open(str(tmp), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(RATE)

            def read_mixed_block():
                nonlocal input_index
                nmax = min(block_size, frames - input_index)
                if not nmax:
                    return np.empty(0, dtype=np.complex128)
                raw = np.frombuffer(inp.readframes(nmax), dtype="<i2")
                if len(raw) != 2 * nmax:
                    raise ValueError("Truncated WAV IQ samples")
                i = raw[::2].astype(np.float64) / 32768
                q = raw[1::2].astype(np.float64) / 32768
                theta = -2 * np.pi * delta * (
                    input_index + np.arange(nmax, dtype=np.float64)
                ) / fs
                input_index += nmax
                return (i + 1j * q) * np.exp(1j * theta)

            left = np.zeros(halo, dtype=np.complex128)
            current = read_mixed_block()
            following = read_mixed_block()
            while len(current):
                original_size = len(current)
                # Only the final block may be shorter than one denominator.
                pad = (-original_size) % down
                centered = np.pad(current, (0, pad)) if pad else current
                future = following[:halo]
                right = np.pad(future, (0, halo-len(future)))
                combined = np.concatenate((left, centered, right))
                downsampled = resample_poly(combined, up, down, window=taps)
                first = halo * up // down
                last = (halo + len(centered)) * up // down
                selected = downsampled[first:last]
                # Last padded block may generate more than ceil(real length*up/down).
                selected = selected[:max(0, expected - written)]
                if len(selected):
                    pcm = np.empty(len(selected) * 2, dtype="<i2")
                    pcm[::2] = np.clip(np.round(selected.real * 32767),
                                      -32768, 32767).astype("<i2")
                    pcm[1::2] = np.clip(np.round(selected.imag * 32767),
                                       -32768, 32767).astype("<i2")
                    out.writeframesraw(pcm.tobytes())
                    written += len(selected)
                left = centered[-halo:]
                current = following
                following = read_mixed_block()

        if written != expected:
            raise RuntimeError(f"Output IQ frame count {written} != {expected}")
        # Atomic no-clobber publication: a concurrent writer cannot be replaced.
        os.link(tmp, dest)
        return {
            "input_rate": fs, "output_rate": RATE, "frames": written,
            "resample_up": up, "resample_down": down,
            "center_hz": center_hz, "target_hz": target_hz,
            "capture_metadata_checked": metadata_checked,
            "capture_integrity_verified": integrity_verified,
            "provenance_verified": False,
        }
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
