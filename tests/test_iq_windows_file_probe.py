"""Synthetic tests for per-file Windows native-crash diagnostics (no RF)."""
from types import SimpleNamespace

import pytest

from scripts import ci_windows_file_probe as probe


def test_per_file_probe_collects_and_reports_all_failing_files(monkeypatch, capsys):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if "--collect-only" in command:
            return SimpleNamespace(returncode=0, stdout=(
                "tests/test_z.py::test_z\n"
                "tests/test_a.py::test_a\n"
                "tests/test_z.py::test_z2\n"
            ), stderr="")
        return SimpleNamespace(returncode=86 if command[-1] == "tests/test_a.py" else 0)

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe_non_iq_files(30) == 1
    assert [c[0][-1] for c in calls[1:]] == ["tests/test_a.py", "tests/test_z.py"]
    assert all("scripts/ci_windows_pytest.py" in c[0] for c in calls[1:])
    assert all(c[1]["timeout"] == 30 for c in calls)
    output = capsys.readouterr().out
    assert "tests/test_a.py: exit=86" in output
    assert "FILE-PROBE FAILURES 1/2" in output


def test_per_file_probe_clean_run(monkeypatch, capsys):
    def fake_run(command, **kwargs):
        if "--collect-only" in command:
            return SimpleNamespace(returncode=0, stdout="tests/test_a.py::test_a\n", stderr="")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe_non_iq_files() == 0
    assert "full-suite QA still required" in capsys.readouterr().out


def test_per_file_probe_rejects_empty_or_failed_collection(monkeypatch):
    for status, output in [(0, "no tests collected"), (2, "collection error")]:
        monkeypatch.setattr(probe.subprocess, "run", lambda *a, status=status, output=output,
                            **kw: SimpleNamespace(returncode=status, stdout=output, stderr=""))
        assert probe.probe_non_iq_files() == 2


def test_per_file_probe_detects_timeout_and_continues(monkeypatch, capsys):
    calls = []

    def fake_run(command, **kwargs):
        if "--collect-only" in command:
            return SimpleNamespace(returncode=0, stdout=(
                "tests/test_a.py::test_a\ntests/test_b.py::test_b\n"), stderr="")
        calls.append(command[-1])
        if command[-1] == "tests/test_a.py":
            raise probe.subprocess.TimeoutExpired(command, 5)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe_non_iq_files(5) == 1
    assert calls == ["tests/test_a.py", "tests/test_b.py"]
    assert "timeout>5s" in capsys.readouterr().out


def test_per_file_probe_rejects_invalid_timeout():
    with pytest.raises(ValueError):
        probe.probe_non_iq_files(0)


def test_file_probe_workflow_is_experimental_only_and_no_installer():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] / ".github" /
                "workflows" / "build.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  windows-file-probe:", 1)[1].split(
        "\n  windows-exe:", 1)[0]
    assert "needs: windows-tests" in job
    assert "needs.windows-tests.result == 'failure'" in job
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in job
    assert "PT2VHF_TEST_EXIT_MODE: hard" in job
    assert "python -m scripts.ci_windows_file_probe" in job
    assert "gh release create" not in job
    assert "pyinstaller" not in job.lower()
