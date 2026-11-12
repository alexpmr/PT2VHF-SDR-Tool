"""Cheap, platform-independent tests for experimental Windows exit-delay isolation."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ci_windows_exit_delay_probe as probe
from scripts import run_tests as runner


def test_probe_fails_closed_and_preserves_baseline(monkeypatch, capsys):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        if kw["env"]["PT2VHF_TEST_EXIT_DELAY_MS"] == "0":
            return SimpleNamespace(returncode=0, stdout="1 passed\n",
                                   stderr="Windows fatal exception: access violation")
        return SimpleNamespace(returncode=0, stdout="1 passed\n", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert probe.probe(10, (0, 1000)) == 1
    assert len(calls) == 8
    assert all(c[1]["env"]["PT2VHF_TEST_EXIT_MODE"] == "hard" for c in calls)
    assert all(c[1]["env"]["PT2VHF_QT_TEST_TEARDOWN"] == "baseline" for c in calls)
    assert "EXIT-DELAY SUMMARY {0: 4, 1000: 0}" in capsys.readouterr().out


def test_probe_rejects_nonzero_status_and_timeout(monkeypatch):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=9, stdout="1 passed", stderr=""))
    assert probe.probe(2, (250,)) == 1

    def timeout(*args, **kwargs):
        raise probe.subprocess.TimeoutExpired(args[0], 2)

    monkeypatch.setattr(probe.subprocess, "run", timeout)
    assert probe.probe(2, (0,)) == 1


def test_probe_rejects_invalid_inputs():
    for seconds, delays in [(0, (0,)), (5, ()), (5, (42,))]:
        with pytest.raises(ValueError):
            probe.probe(seconds, delays)


def test_runner_delay_default_and_validation(monkeypatch):
    class ExitCalled(Exception):
        pass

    import time
    sleep_calls = []
    monkeypatch.setattr(pytest, "main", lambda args: 0)
    monkeypatch.setattr(runner.os, "_exit", lambda code: (_ for _ in ()).throw(ExitCalled(code)))
    monkeypatch.setattr(time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(runner.sys, "argv", ["run_tests.py"])
    monkeypatch.setenv("PT2VHF_TEST_EXIT_MODE", "hard")

    monkeypatch.delenv("PT2VHF_TEST_EXIT_DELAY_MS", raising=False)
    with pytest.raises(ExitCalled):
        runner.main()
    assert not sleep_calls

    monkeypatch.setenv("PT2VHF_TEST_EXIT_DELAY_MS", "250")
    with pytest.raises(ExitCalled):
        runner.main()
    assert sleep_calls == [0.25]

    monkeypatch.setenv("PT2VHF_TEST_EXIT_DELAY_MS", "30000")
    with pytest.raises(ValueError, match="PT2VHF_TEST_EXIT_DELAY_MS"):
        runner.main()


def test_workflow_retires_exhausted_delay_probe():
    # CI #412 reproduced all 16 crashes with 0, 250, 1000 and 2000 ms.
    # Keep the historical probe script for reproducibility but do not rerun
    # the same diagnostic on every push without a new timing hypothesis.
    workflow = (Path(__file__).resolve().parents[1] / ".github" /
                "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "\n  windows-exit-delay-probe:" not in workflow
