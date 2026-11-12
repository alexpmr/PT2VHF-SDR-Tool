"""Cheap, platform-independent regression tests for Windows exit-mechanism diagnostics."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ci_windows_exit_mechanism_probe as probe


def test_commands_are_isolated_and_terminate_bypasses_crt():
    case = probe.SUSPECT_CASES[0]
    assert probe.command_for("hard", case)[1:] == ["scripts/ci_windows_pytest.py", case]
    assert probe.command_for("normal", case)[1:] == ["scripts/ci_windows_pytest.py", case]
    cmd = probe.command_for("terminate", case)
    assert cmd[:3] == [probe.sys.executable, "-X", "faulthandler"]
    assert "TerminateProcess" in cmd[4]
    assert "os._exit" not in cmd[4]
    assert cmd[-1] == case
    with pytest.raises(ValueError):
        probe.command_for("bad", case)
    with pytest.raises(ValueError):
        probe.command_for("terminate", "not-a-real-test")


def test_probe_preserves_crash_detection_and_does_not_certify(monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        if kw["env"]["PT2VHF_TEST_EXIT_MODE"] == "hard" and cmd[1] != "-X":
            return SimpleNamespace(returncode=0, stdout="1 passed\n",
                                   stderr="Windows fatal exception: access violation")
        return SimpleNamespace(returncode=0, stdout="1 passed\n", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe(15) == 1
    assert len(calls) == 6
    assert all(c[1]["env"]["PT2VHF_QT_TEST_TEARDOWN"] == "baseline" for c in calls)
    assert all(c[1]["timeout"] == 15 for c in calls)
    output = capsys.readouterr().out
    assert "EXIT-MECHANISM SUMMARY {'hard': 2, 'normal': 0, 'terminate': 0}" in output
    assert "not Windows QA" in output
    assert "bypasses DLL detach" in output


def test_nonzero_timeout_and_invalid_options_fail_closed(monkeypatch):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw:
                        SimpleNamespace(returncode=7, stdout="1 passed", stderr=""))
    assert probe.probe(5, ("terminate",)) == 1

    def timeout(*args, **kwargs):
        raise probe.subprocess.TimeoutExpired(args[0], 5)

    monkeypatch.setattr(probe.subprocess, "run", timeout)
    assert probe.probe(5, ("normal",)) == 1
    for seconds, modes in ((0, ("hard",)), (5, ()), (5, ("unsafe",))):
        with pytest.raises(ValueError):
            probe.probe(seconds, modes)


def test_retired_exit_mechanism_job_stays_disabled_and_replacement_is_safe():
    """The historical probe script remains testable but no longer runs on each CI."""
    workflow = (Path(__file__).resolve().parents[1] / ".github" /
                "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "\n  windows-exit-mechanism-probe:" not in workflow
    assert "\n  windows-qt-runtime-probe:" not in workflow
    job = workflow.split("\n  windows-file-probe:", 1)[1].split(
        "\n  windows-case-probe:", 1
    )[0]
    assert "needs: windows-tests" in job
    assert "needs.windows-tests.result == 'failure'" in job
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in job
    assert "python -m scripts.ci_windows_file_probe" in job
    assert "pyinstaller" not in job.lower()
    assert "gh release create" not in job
