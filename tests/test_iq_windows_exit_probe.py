"""Synthetic regression coverage for the Windows minimal Qt exit probe."""
from types import SimpleNamespace

import pytest

from scripts import ci_windows_exit_probe as probe


def test_matrix_and_exit_paths():
    assert set(probe.SCENARIOS) == {"bare", "qt_import", "qt_widget", "main_window"}
    assert probe.EXIT_MODES == ("hard", "normal")
    assert "os._exit(0)" in probe.child_code("qt_widget", "hard")
    assert "raise SystemExit(0)" in probe.child_code("qt_widget", "normal")
    assert "MainWindow()" in probe.child_code("main_window", "normal")
    for bad_scenario, bad_mode in [("oops", "hard"), ("bare", "oops")]:
        with pytest.raises(ValueError):
            probe.child_code(bad_scenario, bad_mode)


def test_probe_runs_all_cases_and_checks_ready(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stdout="EXIT-PROBE-READY\n", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe(8) == 0
    assert len(calls) == 8
    assert all(c[0][1:4] == ["-X", "faulthandler", "-c"] for c in calls)
    assert all(c[1]["timeout"] == 8 and c[1]["env"]["QT_QPA_PLATFORM"] == "offscreen" for c in calls)


@pytest.mark.parametrize("stdout,stderr,returncode", [
    ("EXIT-PROBE-READY\n", "Windows fatal exception: access violation", 0),
    ("EXIT-PROBE-READY\n", "", 3),
    ("", "", 0),
])
def test_probe_fails_closed(monkeypatch, stdout, stderr, returncode):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr))
    assert probe.probe(5) == 1


def test_probe_catches_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise probe.subprocess.TimeoutExpired(cmd, 5)
    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe(5) == 1
    with pytest.raises(ValueError):
        probe.probe(0)


def test_workflow_exit_probe_is_diagnostic_only():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] / ".github" /
                "workflows" / "build.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  windows-exit-probe:", 1)[1].split("\n  windows-exe:", 1)[0]
    assert "needs: windows-case-probe" in job
    assert "needs.windows-case-probe.result == 'failure'" in job
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in job
    assert "python -m scripts.ci_windows_exit_probe" in job
    assert "gh release create" not in job
    assert "pyinstaller" not in job.lower()
