"""Synthetic-only checks for pipeline coverage masked across SDRs.

No RF recordings or independent labels are used in these regression tests.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.iq_session_gate as gate
from pt2vhf.dsp.iq_classifier import CLASSES


def test_observations_reports_worst_sdr_session_inference_coverage(monkeypatch):
    # One shared session: 100/100 windows inferred on SDR-A, but only
    # 1/10 on SDR-B. Session aggregate 101/110 > 0.80 must not hide SDR-B.
    def fake_read_windows(path, max_windows, *, stats):
        if path.name == "sdr-a.wav":
            selected, inferred = 100, 100
        else:
            selected, inferred = 10, 1
        stats.update(selected=selected, skipped_silence=selected - inferred)
        for _ in range(inferred):
            yield object()

    class PerfectAM:
        def predict(self, iq):
            return SimpleNamespace(probabilities={
                name: (1.0 if name == "AM" else 0.0) for name in CLASSES
            })

    monkeypatch.setattr(gate, "read_windows", fake_read_windows)
    rows = [
        (Path("sdr-a.wav"), "AM", "shared-session", "sdr-a"),
        (Path("sdr-b.wav"), "AM", "shared-session", "sdr-b"),
    ]
    accounting = {}
    predictions = gate.observations(rows, PerfectAM(), 100, accounting=accounting)
    assert len(predictions) == 101
    assert accounting["minimum_session_pipeline_coverage"] == pytest.approx(101 / 110)
    assert accounting["minimum_device_session_pipeline_coverage"] == pytest.approx(0.1)
    assert accounting["device_session_cells"] == 2
    assert accounting["windows_selected"] == 110
    assert accounting["windows_inferred"] == 101
    assert "sdr-a" not in json.dumps(accounting)
    assert "shared-session" not in json.dumps(accounting)


@pytest.mark.parametrize("bad_cell, expected", [
    (True, "HOLDOUT_INSUFFICIENT_PIPELINE_COVERAGE"),
    (False, "HOLDOUT_EVALUATED"),
])
def test_holdout_rejects_hidden_device_session_pipeline_gap(
        monkeypatch, bad_cell, expected):
    # Fully replicated synthetic mode x SDR holdout, with perfect scores.
    # Only the pipeline-coverage stratum changes between the two cases.
    devices = ("sdr-a", "sdr-b")
    modes = (*gate.REQUIRED_KNOWN_CLASSES, "UNKNOWN")
    cal = [
        (Path(f"cal-{mode}-{device}.wav"), mode,
         "cal-unknown" if mode == "UNKNOWN" else "cal-known", device)
        for device in devices for mode in modes
    ]
    hold = [
        (Path(f"hold-{mode}-{device}-{index}.wav"), mode,
         f"hold-{'unknown' if mode == 'UNKNOWN' else 'known'}-{index}", device)
        for device in devices for mode in modes for index in (1, 2)
    ]
    monkeypatch.setattr(gate, "audit", lambda *args: (cal, hold))

    def fake_observations(rows, model, max_windows, *, accounting=None):
        if accounting is not None:
            accounting.update({
                "minimum_session_pipeline_coverage": .95,
                "minimum_device_session_pipeline_coverage": (
                    .10 if rows is hold and bad_cell else .95),
                "device_session_cells": 4 if rows is hold else 2,
            })
        return [(mode, mode, .99, session, device)
                for _path, mode, session, device in rows]

    monkeypatch.setattr(gate, "observations", fake_observations)
    result = gate.run(Path("cal.json"), Path("hold.json"), Path("."), object())
    assert result["decision"] == expected
    assert result["holdout_class_device_session_diversity_gate_passed"]
    assert result["holdout_class_device_coverage_gate_passed"]
    assert result["holdout_diversity_gate_passed"]
    assert result["operationally_validated"] is False
