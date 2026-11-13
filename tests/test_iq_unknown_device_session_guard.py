"""Synthetic-only guard against UNKNOWN false-acceptance masked across SDR/session.

These observations are constructed test fixtures, not real RF measurements.
"""
import json

import pytest

from scripts.iq_session_gate import rates, select


def _rows():
    # Session 'shared' spans two SDRs. One SDR has 100% UNKNOWN false
    # acceptance in this session, but 19 clean UNKNOWN windows in another
    # session. The other SDR has 19 clean windows in 'shared'.
    known = [
        ("AM", "AM", .99, "known-a", "sdr-a"),
        ("AM", "AM", .99, "known-b", "sdr-b"),
    ]
    unknown = [
        ("UNKNOWN", "UNKNOWN", .99, "shared", "sdr-a")
        for _ in range(19)
    ]
    unknown += [
        ("UNKNOWN", "UNKNOWN", .99, "other", "sdr-b")
        for _ in range(19)
    ]
    unknown.append(("UNKNOWN", "AM", .99, "shared", "sdr-b"))
    return known + unknown


def test_unknown_worst_device_session_prevents_marginal_masking():
    rows = _rows()
    report = rates(rows, .95)
    assert report["unknown_false_accept_rate"] == pytest.approx(1 / 39)
    assert report["unknown_worst_session_false_accept_rate"] == pytest.approx(1 / 20)
    assert report["unknown_worst_device_false_accept_rate"] == pytest.approx(1 / 20)
    assert report["unknown_worst_device_session_false_accept_rate"] == 1.0
    assert report["unknown_device_session_cells_observed"] == 3
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is None
    assert "sdr-a" not in json.dumps(report)
    assert "sdr-b" not in json.dumps(report)
    assert "shared" not in json.dumps(report)


def test_unknown_device_session_guard_positive_control_and_legacy_rows():
    rows = _rows()
    rows[-1] = ("UNKNOWN", "UNKNOWN", .99, "shared", "sdr-b")
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is not None
    assert chosen["unknown_worst_device_session_false_accept_rate"] == 0.0
    assert chosen["unknown_device_session_cells_observed"] == 3

    # The standalone legacy four-field rate API has no device metadata.
    # It must not fabricate a device-level statistic.
    legacy = rates([row[:4] for row in rows], .95)
    assert legacy["unknown_worst_device_session_false_accept_rate"] is None
    assert legacy["unknown_device_session_cells_observed"] is None
