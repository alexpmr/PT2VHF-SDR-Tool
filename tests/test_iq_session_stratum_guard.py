"""Synthetic-only regression for worst-session IQ/OOD gates.

These fabricated observations do not represent RF captures, model accuracy,
hardware diversity or operational acceptance.
"""
import json

import pytest

from scripts.iq_session_gate import rates, select


def test_single_bad_unknown_session_cannot_hide_behind_other_sessions():
    known = [("AM", "AM", .99, "known-a", "sdr-a"),
             ("AM", "AM", .99, "known-b", "sdr-b")]
    unknown = [
        ("UNKNOWN", "UNKNOWN", .99, f"quiet-a-{i}", "sdr-a")
        for i in range(20)
    ] + [
        ("UNKNOWN", "UNKNOWN", .99, f"quiet-b-{i}", "sdr-b")
        for i in range(20)
    ] + [("UNKNOWN", "AM", .99, "bad-unknown", "sdr-a")]
    rows = known + unknown
    measured = rates(rows, .95)
    assert measured["unknown_false_accept_rate"] == pytest.approx(1 / 41)
    assert measured["unknown_session_macro_false_accept"] == pytest.approx(1 / 41)
    assert measured["unknown_worst_device_false_accept_rate"] == pytest.approx(1 / 21)
    assert measured["unknown_worst_session_false_accept_rate"] == 1.0
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is None
    assert "bad-unknown" not in json.dumps(measured)


def test_failed_cw_session_cannot_hide_within_same_class_and_sdr():
    known = (
        [("CW", "CW", .99, "cw-a-good", "sdr-a") for _ in range(100)]
        + [("CW", "AM", .99, "cw-a-bad", "sdr-a")]
        + [("CW", "CW", .99, "cw-b-good", "sdr-b") for _ in range(100)]
        + [("AM", "AM", .99, "am-a-good", "sdr-a") for _ in range(100)]
        + [("AM", "AM", .99, "am-b-good", "sdr-b") for _ in range(100)]
    )
    unknown = [("UNKNOWN", "UNKNOWN", .99, "noise-a", "sdr-a"),
               ("UNKNOWN", "UNKNOWN", .99, "noise-b", "sdr-b")]
    rows = known + unknown
    measured = rates(rows, .95)
    assert measured["known_worst_class_session_macro_coverage"] == pytest.approx(2 / 3)
    assert measured["known_worst_class_device_correct_coverage"] == pytest.approx(100 / 101)
    assert measured["known_worst_class_device_session_correct_coverage"] == 0.0
    assert measured["known_class_device_session_cells_observed"] == 5
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is None
    assert "cw-a-bad" not in json.dumps(measured)


def test_stratum_controls_and_legacy_rate_api():
    rows = [
        ("CW", "CW", .99, "cw-a", "sdr-a"),
        ("CW", "CW", .99, "cw-b", "sdr-b"),
        ("AM", "AM", .99, "am-a", "sdr-a"),
        ("AM", "AM", .99, "am-b", "sdr-b"),
        ("UNKNOWN", "UNKNOWN", .99, "noise-a", "sdr-a"),
        ("UNKNOWN", "UNKNOWN", .99, "noise-b", "sdr-b"),
    ]
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is not None
    assert chosen["known_worst_class_device_session_correct_coverage"] == 1.0
    assert chosen["known_class_device_session_cells_observed"] == 4
    assert chosen["unknown_worst_session_false_accept_rate"] == 0.0
    legacy = rates([row[:4] for row in rows], .95)
    assert legacy["known_worst_class_device_session_correct_coverage"] is None
    assert legacy["known_class_device_session_cells_observed"] is None
    assert legacy["unknown_worst_session_false_accept_rate"] == 0.0
