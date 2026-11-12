"""Synthetic regression tests for the experimental Windows case probe."""
from types import SimpleNamespace

import pytest

from scripts import ci_windows_case_probe as probe


def _collected():
    return ("tests/test_v010_ui.py::test_one\n"
            "tests/test_v050_ui.py::test_two\n"
            "2 tests collected in 0.01s\n")


def test_case_parser_filters_summaries_other_files_and_deduplicates():
    raw = _collected() + "tests/test_other.py::test_bad\n" + "tests\\test_v010_ui.py::test_one\n"
    assert probe.parse_case_ids(raw) == ["tests/test_v010_ui.py::test_one", "tests/test_v050_ui.py::test_two"]


def test_probe_runs_each_case_in_both_modes_and_reports_failure(monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        if "--collect-only" in cmd:
            return SimpleNamespace(returncode=0, stdout=_collected(), stderr="")
        return SimpleNamespace(returncode=86 if kw["env"]["PT2VHF_TEST_EXIT_MODE"] == "normal" and
                               cmd[-1].endswith("test_two") else 0, stdout="native crash", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe_cases(30) == 1
    assert len(calls) == 5
    assert all(c[1]["timeout"] == 30 for c in calls)
    assert all(c[0][1] == "scripts/ci_windows_pytest.py" for c in calls[1:])
    assert [c[1]["env"]["PT2VHF_TEST_EXIT_MODE"] for c in calls[1:]] == ["hard", "hard", "normal", "normal"]
    assert "normal tests/test_v050_ui.py::test_two: exit=86" in capsys.readouterr().out


def test_probe_rejects_missing_file_and_collection_errors(monkeypatch):
    for rc, out in [(0, "tests/test_v010_ui.py::test_one\n"), (2, "collection failed")]:
        monkeypatch.setattr(probe.subprocess, "run", lambda *a, rc=rc, out=out, **k:
                            SimpleNamespace(returncode=rc, stdout=out, stderr=""))
        assert probe.probe_cases(5) == 2


def test_probe_handles_timeout_and_continues(monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kw):
        if "--collect-only" in cmd:
            return SimpleNamespace(returncode=0, stdout=_collected(), stderr="")
        calls.append(cmd[-1])
        if cmd[-1].endswith("test_one"):
            raise probe.subprocess.TimeoutExpired(cmd, 5)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe_cases(5, ("hard",)) == 1
    assert len(calls) == 2
    assert "timeout>5s" in capsys.readouterr().out


def test_probe_rejects_invalid_inputs():
    for seconds, modes in [(0, ("hard",)), (30, ()), (30, ("oops",))]:
        with pytest.raises(ValueError):
            probe.probe_cases(seconds, modes)


def test_case_probe_workflow_is_experimental_and_no_installer():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] / ".github" /
                "workflows" / "build.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  windows-case-probe:", 1)[1].split("\n  windows-exe:", 1)[0]
    assert "needs: windows-file-probe" in job
    assert "needs.windows-file-probe.result == 'failure'" in job
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in job
    assert "python -m scripts.ci_windows_case_probe --timeout-seconds 180 --exit-mode hard" in job
    # QPA is the single new experimental variable. The normal Windows lane
    # must remain offscreen and fail closed; this diagnostic is not QA approval.
    assert "QT_QPA_PLATFORM: minimal" in job
    assert "QT_QPA_PLATFORM: offscreen" not in job
    assert "gh release create" not in job
    assert "pyinstaller" not in job.lower()
