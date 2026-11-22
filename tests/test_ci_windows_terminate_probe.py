"""Pure synthetic guards for the one-shot Windows termination diagnostic.

No test calls TerminateProcess, opens a debugger or asserts that a successful
diagnostic constitutes Windows QA or RF/ONNX model validation.
"""
import sys

import pytest

from scripts import ci_windows_terminate_probe as probe


@pytest.mark.parametrize("code,fatal,expected", [
    (0, False, 0), (0, True, 86), (1, False, 1),
    (1, True, 1), (3221225477, True, 3221225477),
])
def test_probe_exit_status_is_fail_closed(code, fatal, expected):
    assert probe.probe_exit_status(code, fatal) == expected


def test_terminate_process_rejects_non_windows_without_native_call(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="Windows-only"):
        probe.terminate_current_process(0)


def test_one_shot_probe_is_never_mandatory_or_release_lane():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    lane = workflow.split("\n  windows-terminate-exit-probe:", 1)[1].split(
        "\n  windows-exe:", 1)[0]
    assert "contains(github.event.head_commit.message, '[probe-terminate-exit]')" in lane
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in lane
    assert "scripts/ci_windows_terminate_probe.py" in lane
    mandatory = workflow.split("\n  windows-tests:", 1)[1].split(
        "\n  windows-crash-isolation:", 1)[0]
    assert "python scripts/ci_windows_pytest.py" in mandatory
    assert "ci_windows_terminate_probe" not in mandatory
