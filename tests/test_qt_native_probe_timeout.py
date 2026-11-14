"""Regression coverage for native Qt subprocess hang diagnostics (no SDR hardware)."""
from __future__ import annotations

import subprocess

from scripts import probe_qt_native_exit as probe


def test_timeout_retains_partial_child_phases(monkeypatch, capsys, tmp_path):
    def fake_run(cmd, **kwargs):
        assert kwargs["env"]["PT2VHF_QT_PROBE_TRACE"] == "1"
        assert kwargs["timeout"] == 7
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=7,
            output=b"CHILD-PHASE scenario=graphics phase=graphics-plot-ready\n",
        )

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    result = probe.parent(
        repeats=1,
        frames=1,
        timeout=7,
        source_root=tmp_path,
        scenarios=("graphics",),
        exit_modes=("hard",),
    )
    captured = capsys.readouterr().out
    assert result == 1
    assert "graphics/hard #1: TIMEOUT (7s)" in captured
    assert "CHILD-OUTPUT-BEFORE-TIMEOUT:" in captured
    assert "phase=graphics-plot-ready" in captured
    assert "NATIVE-EXIT-FAILURES:" in captured


def test_timeout_without_child_output_still_fails(monkeypatch, capsys, tmp_path):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=3)

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    result = probe.parent(
        repeats=1,
        frames=1,
        timeout=3,
        source_root=tmp_path,
        scenarios=("bare",),
        exit_modes=("normal",),
    )
    captured = capsys.readouterr().out
    assert result == 1
    assert "(no child output)" in captured


def test_successful_child_exit_remains_required(monkeypatch, capsys, tmp_path):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=0,
            stdout="CHILD-READY scenario=bare exit=normal frames=1\n",
        )

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    result = probe.parent(
        repeats=1,
        frames=1,
        timeout=3,
        source_root=tmp_path,
        scenarios=("bare",),
        exit_modes=("normal",),
    )
    assert result == 0
    assert "probes passed" in capsys.readouterr().out
