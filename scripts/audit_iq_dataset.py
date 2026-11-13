"""Offline IQ WAV quality preflight. NOT RF validation or model identification.

Reports omit paths/session identifiers; files and labels never leave the machine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from collections import defaultdict
from pathlib import Path

import numpy as np

WINDOW = 2048
RATE = 48000


def inspect_recording(path: Path, *, max_windows: int = 256) -> dict:
    """Inspect uniformly spaced PCM16 IQ windows across the entire recording."""
    if max_windows < 1:
        raise ValueError("max_windows must be >= 1")
    hashes = set()
    quiet = flat = clipped = samples = windows = 0
    power_sum = dc_sum = edge_sum = corr_sum = 0.0
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(),
                wav.getcomptype()) != (2, 2, RATE, "NONE"):
            raise ValueError("Expected 48 kHz, stereo PCM16 WAV IQ (left I, right Q)")
        frames = wav.getnframes()
        available = frames // WINDOW
        count = min(max_windows, available)
        # Bounded, deterministic coverage across the *whole* recording.
        # The former prefix-only scan missed late clipping and reused IQ.
        for ordinal in range(count):
            index = (ordinal * (available - 1) // (count - 1)
                     if count > 1 else (available - 1) // 2)
            wav.setpos(index * WINDOW)
            raw = wav.readframes(WINDOW)
            if len(raw) != WINDOW * 4:
                raise ValueError("Truncated PCM IQ window")
            pcm = np.frombuffer(raw, dtype="<i2").reshape(WINDOW, 2)
            v = pcm.astype(np.float64) / 32768
            i, q = v[:, 0], v[:, 1]
            z = i + 1j * q
            rms = float(np.sqrt(np.mean(i*i + q*q) / 2))
            power_sum += rms * rms
            if rms < .001:
                quiet += 1
            else:
                hashes.add(hashlib.sha256(raw).digest())
            clipped += int(np.count_nonzero(np.abs(pcm.astype(np.int32)) >= 32760))
            flat += int(np.count_nonzero(np.all(np.diff(pcm, axis=0) == 0, axis=1)))
            samples += 2 * WINDOW
            windows += 1
            dc_sum += float(abs(z.mean()) / max(np.sqrt(np.mean(np.abs(z)**2)), 1e-12))
            centered = z - z.mean()
            power = np.abs(np.fft.fft(centered * np.hanning(WINDOW)))**2
            freqs = np.fft.fftfreq(WINDOW, 1 / RATE)
            edge_sum += float(power[np.abs(freqs) >= 20000].sum() /
                              max(power.sum(), 1e-30))
            ia, qa = i - i.mean(), q - q.mean()
            denom = math.sqrt(float(np.dot(ia, ia) * np.dot(qa, qa)))
            corr_sum += float(abs(np.dot(ia, qa) / denom)) if denom > 1e-15 else 0.0
    if not windows:
        raise ValueError("Recording has no complete 2048-sample IQ windows")
    return {
        "frames_total": frames,
        "windows_available": available,
        "windows_inspected": windows,
        "window_selection": "uniform_full_recording_nonoverlapping",
        "rms_dbfs_mean": round(20 * math.log10(max(math.sqrt(power_sum / windows), 1e-12)), 2),
        "quiet_window_rate": quiet / windows,
        "clipping_sample_rate": clipped / samples,
        "flat_pair_rate": flat / (windows * (WINDOW - 1)),
        "mean_dc_to_rms": dc_sum / windows,
        "mean_edge_power_rate": edge_sum / windows,
        "mean_abs_iq_correlation": corr_sum / windows,
        "unique_nonquiet_windows": len(hashes),
        "_fingerprints": hashes,
    }


def _assess(metrics: dict, mode: str) -> list[str]:
    flags = []
    if metrics["quiet_window_rate"] >= .99:
        flags.append("BLOCK: almost_all_windows_quiet")
    elif metrics["quiet_window_rate"] > .10:
        flags.append("REVIEW: quiet_windows")
    if metrics["clipping_sample_rate"] >= .20:
        flags.append("BLOCK: heavy_adc_or_pcm_clipping")
    elif metrics["clipping_sample_rate"] > .005:
        flags.append("REVIEW: clipped_samples")
    if metrics["flat_pair_rate"] >= .95:
        if metrics["quiet_window_rate"] < .99 and mode in ("CW", "AM", "UNKNOWN"):
            # A genuine zero-beat carrier and receiver DC are indistinguishable
            # from these PCM samples. UNKNOWN must include unmodulated OOD
            # carriers, so demand external review instead of deleting the
            # negative-control population before evaluating neural rejection.
            flags.append(
                "REVIEW: constant_unknown_carrier_or_hardware_dc"
                if mode == "UNKNOWN" else "REVIEW: constant_cw_am_or_hardware_dc")
        else:
            flags.append("BLOCK: nearly_constant_iq_samples")
    if metrics["windows_inspected"] < 10:
        flags.append("REVIEW: short_recording")
    # Do not silently label a high coherent-DC component as known RF.
    # In CW/AM it may be a legitimate centered carrier OR receiver DC spur.
    if mode in ("AM", "CW") and metrics["mean_dc_to_rms"] > .85:
        flags.append("REVIEW: centered_carrier_or_hardware_dc_spur")
    elif mode not in ("AM", "CW") and metrics["mean_dc_to_rms"] > .55:
        flags.append("REVIEW: high_dc_component_check_centering")
    if mode in ("NFM", "USB", "LSB") and metrics["mean_abs_iq_correlation"] > .995:
        flags.append("REVIEW: suspicious_stereo_channel_correlation")
    if metrics["mean_edge_power_rate"] > .35:
        flags.append("REVIEW: high_near_nyquist_power")
    return flags


def audit_dataset(manifest: Path, root: Path, *, max_windows: int = 256) -> dict:
    from scripts.evaluate_iq_recordings import read_manifest
    records = read_manifest(manifest, root)
    owners = defaultdict(set)
    entries, sessions = [], set()
    for idx, (path, mode, session, _device) in enumerate(records):
        values = inspect_recording(path, max_windows=max_windows)
        fingerprints = values.pop("_fingerprints")
        entries.append({"index": idx, "mode": mode,
                        "metrics": values, "flags": _assess(values, mode)})
        sessions.add(session)
        for fingerprint in fingerprints:
            owners[fingerprint].add((session, idx))
    leaked = set()
    for holders in owners.values():
        if len({session for session, _ in holders}) > 1:
            leaked.update(i for _, i in holders)
    for entry in entries:
        if entry["index"] in leaked:
            entry["flags"].append("BLOCK: identical_iq_window_across_sessions")
    blocked = sum(any(x.startswith("BLOCK:") for x in e["flags"]) for e in entries)
    review = sum(bool(e["flags"]) and not any(x.startswith("BLOCK:") for x in e["flags"])
                 for e in entries)
    return {
        "scope": "Offline IQ data QA; NOT field or RF model validation",
        "status": "BLOCK" if blocked else "REVIEW" if review else "PASS",
        "rf_validated": False,
        "operator_labels_verified": False,
        "recordings": len(entries),
        "sessions": len(sessions),
        "blocked_recordings": blocked,
        "review_recordings": review,
        "entries": entries,
        "limitations": (
            "Heuristic flags may include legitimate weak AM/CW or unmodulated "
            "UNKNOWN carriers; constant IQ needs independent DC/RF review. "
            "Exact window reuse does not detect shifted or modified copies. PASS only means no "
            "listed anomalies were observed; it does not validate RF accuracy."),
    }


def main():
    p = argparse.ArgumentParser(description="Offline IQ WAV quality and leakage audit")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-windows", type=int, default=256)
    args = p.parse_args()
    report = audit_dataset(args.manifest, args.root, max_windows=args.max_windows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"IQ QA: {report['status']}; {report['recordings']} files; "
          f"{report['blocked_recordings']} blocked; "
          f"{report['review_recordings']} to review")
    if report["status"] == "BLOCK":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
