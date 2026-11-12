"""Deterministic regression tests for optional Windows native CI diagnostics.

These tests do not crash the process, nor claim to isolate the responsible DLL.
"""
from __future__ import annotations

import threading

from scripts import ci_native_lifecycle as census


def test_snapshot_counts_python_threads_and_native_threads(monkeypatch):
    monkeypatch.setattr(census, "_win_native_thread_count", lambda: 17)
    data = census.snapshot()
    assert data["python_threads"] >= 1
    assert 0 <= data["python_daemon_threads"] <= data["python_threads"]
    assert data["native_threads"] == 17
    assert set(data) == {
        "python_threads", "python_daemon_threads", "native_threads",
        "qt_top_level_widgets", "qt_visible_top_level_widgets",
    }


def test_report_prints_only_aggregate_counts(monkeypatch, capsys):
    monkeypatch.setattr(census, "snapshot", lambda: {
        "python_threads": 2, "python_daemon_threads": 1,
        "native_threads": 5, "qt_top_level_widgets": 0,
        "qt_visible_top_level_widgets": 0,
    })
    census.report("after-pytest")
    output = capsys.readouterr().out
    assert "CI-NATIVE-LIFECYCLE phase=after-pytest" in output
    assert "native_threads=5" in output
    assert "python_daemon_threads=1" in output


def test_report_never_breaks_suite_if_probe_fails(monkeypatch, capsys):
    def fail():
        raise RuntimeError("probe failure is diagnostic only")
    monkeypatch.setattr(census, "snapshot", fail)
    census.report("before-hard-exit")
    assert "unavailable=RuntimeError" in capsys.readouterr().out
