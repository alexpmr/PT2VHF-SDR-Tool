"""Cheap, platform-independent tests for the experimental Qt shutdown probe."""
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from scripts import ci_windows_qt_teardown_probe as diagnostic


def test_fatal_output_rejected_even_with_zero_exit():
    assert diagnostic.is_failed_run(0, "Windows fatal exception: access violation\n")
    assert diagnostic.is_failed_run(3221226356, "1 passed")
    assert not diagnostic.is_failed_run(0, "1 passed in 0.4s")


def test_probe_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        diagnostic.probe(0)
    with pytest.raises(ValueError):
        diagnostic.probe(1, ("unknown",))
    with pytest.raises(ValueError):
        diagnostic.probe(1, ())


def test_probe_compares_both_modes_without_hiding_baseline_failure(capsys):
    results = [SimpleNamespace(returncode=0, stdout="1 passed\nWindows fatal exception: access violation", stderr="")
               for _ in diagnostic.SUSPECT_CASES]
    results += [SimpleNamespace(returncode=0, stdout="1 passed", stderr="")
                for _ in diagnostic.SUSPECT_CASES]
    with patch.object(diagnostic.subprocess, "run", side_effect=results) as run:
        assert diagnostic.probe(3) == 1
    assert run.call_count == 2 * len(diagnostic.SUSPECT_CASES)
    assert "fixture cleanup implicated" in capsys.readouterr().out
    for call in run.call_args_list[:len(diagnostic.SUSPECT_CASES)]:
        assert call.kwargs["env"]["PT2VHF_QT_TEST_TEARDOWN"] == "baseline"
        assert call.kwargs["env"]["PT2VHF_TEST_EXIT_MODE"] == "hard"


def test_probe_detects_skipped_cleanup_failure(capsys):
    results = [SimpleNamespace(returncode=0, stdout="1 passed", stderr="")
               for _ in diagnostic.SUSPECT_CASES]
    results += [SimpleNamespace(returncode=1, stdout="", stderr="")
                for _ in diagnostic.SUSPECT_CASES]
    with patch.object(diagnostic.subprocess, "run", side_effect=results):
        assert diagnostic.probe(3) == 1
    assert "skipping session fixture cleanup is insufficient" in capsys.readouterr().out


def test_probe_timeout_is_failure():
    import subprocess
    with patch.object(diagnostic.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 2)):
        assert diagnostic.probe(2, ("baseline",)) == 1
