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


def test_opt_in_qt_disposal_requests_deferred_delete_only(monkeypatch, capsys):
    import sys
    from types import SimpleNamespace

    class FakeWidget:
        def __init__(self, fails=False):
            self.fails = fails
            self.called = False

        def deleteLater(self):
            self.called = True
            if self.fails:
                raise RuntimeError("stale native widget")

    widgets = [FakeWidget(), FakeWidget(fails=True)]
    processed = []
    class FakeApplication:
        def topLevelWidgets(self):
            return widgets
        def processEvents(self):
            processed.append("process-events")

    app = FakeApplication()
    fake_widgets = SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: app))
    fake_core = SimpleNamespace(
        QCoreApplication=SimpleNamespace(
            sendPostedEvents=lambda target, kind: processed.append((target, kind))),
        QEvent=SimpleNamespace(DeferredDelete=52),
    )
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", fake_widgets)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", fake_core)
    attempted, failed = census.dispose_qt_top_levels()

    assert (attempted, failed) == (2, 1)
    assert all(w.called for w in widgets)
    assert processed == [(None, 52), "process-events"]
    assert "CI-QT-DISPOSAL attempted=2 failed=1" in capsys.readouterr().out


def test_opt_in_qt_disposal_handles_absent_qt(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", None)
    assert census.dispose_qt_top_levels() == (0, 0)


def test_nested_pytest_runner_cannot_trigger_outer_qt_disposal(monkeypatch, capsys):
    """The A/B env must never delete live widgets from mocked runner tests."""
    import sys
    from types import SimpleNamespace
    from scripts import run_tests

    monkeypatch.setenv("PT2VHF_CI_QT_DISPOSE_AFTER_PYTEST", "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "nested-runner (call)")
    monkeypatch.setenv("PT2VHF_TEST_EXIT_MODE", "normal")
    monkeypatch.delenv("PT2VHF_CI_NATIVE_LIFECYCLE", raising=False)
    monkeypatch.setitem(sys.modules, "pytest", SimpleNamespace(main=lambda args: 0))
    monkeypatch.setattr(sys, "argv", ["run_tests.py"])
    assert run_tests.main() == 0
    assert "CI-QT-DISPOSAL skipped=nested-pytest-runner" in capsys.readouterr().out


def test_exhausted_qt_disposal_ab_is_not_scheduled_on_pushes():
    """No repeated native abort experiment; mandatory Windows gate remains."""
    from pathlib import Path

    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "\n  windows-qt-disposal-probe:" not in workflow
    assert "PT2VHF_CI_QT_DISPOSE_AFTER_PYTEST" not in workflow
    mandatory = workflow.split("\n  windows-tests:", 1)[1].split(
        "\n  windows-crash-isolation:", 1
    )[0]
    assert "run: python scripts/ci_windows_pytest.py" in mandatory
    assert "PT2VHF_CI_NATIVE_LIFECYCLE" in mandatory
