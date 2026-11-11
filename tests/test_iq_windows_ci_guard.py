"""Synthetic checks for the Windows native-crash CI guard (no RF)."""
from scripts.ci_windows_pytest import is_fatal_runtime_output, main


def test_fatal_windows_exception_is_not_a_green_test_run():
    assert is_fatal_runtime_output("Windows fatal exception: access violation")
    assert is_fatal_runtime_output("Fatal Python error: Segmentation fault")
    assert is_fatal_runtime_output("Process exited (core dumped)")
    assert not is_fatal_runtime_output("333 passed, 2 skipped in 141.97s")


def test_wrapper_rejects_native_crash_even_with_zero_process_exit(monkeypatch, capsys):
    import scripts.ci_windows_pytest as runner

    class FakeProcess:
        stdout = iter([
            "333 passed, 2 skipped in 141.97s\n",
            "Windows fatal exception: access violation\n",
        ])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def wait(self):
            return 0

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw: FakeProcess())
    assert main() == 86
    assert "Windows QA must not pass" in capsys.readouterr().err


def test_wrapper_preserves_pytest_failures_and_clean_success(monkeypatch):
    import scripts.ci_windows_pytest as runner

    class FakeProcess:
        def __init__(self, output, status):
            self.stdout = iter(output)
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def wait(self):
            return self.status

    for status, output, expected in [
        (0, ["333 passed, 2 skipped\n"], 0),
        (1, ["1 failed\n"], 1),
        (139, ["Fatal Python error: Segmentation fault\n"], 139),
    ]:
        monkeypatch.setattr(
            runner.subprocess, "Popen",
            lambda *a, status=status, output=output, **kw:
                FakeProcess(output, status),
        )
        assert main() == expected


def test_windows_wrapper_forwards_pytest_selection(monkeypatch):
    import sys
    import scripts.ci_windows_pytest as runner

    seen = []

    class FakeProcess:
        stdout = iter(["1 passed, 0 failed\\n"])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def wait(self):
            return 0

    def fake_popen(command, **kwargs):
        seen.append(command)
        return FakeProcess()

    monkeypatch.setattr(sys, "argv", ["ci_windows_pytest.py", "-k", "not iq_"])
    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    assert runner.main() == 0
    assert seen == [[sys.executable, "-X", "faulthandler",
                     "scripts/run_tests.py", "-k", "not iq_"]]


def test_pytest_runner_forwards_selection_and_preserves_exit(monkeypatch):
    import sys
    import types
    import scripts.run_tests as runner

    seen = []
    monkeypatch.setitem(sys.modules, "pytest", types.SimpleNamespace(
        main=lambda args: seen.append(args) or 0
    ))
    monkeypatch.setattr(sys, "argv", ["run_tests.py", "-k", "iq_"])
    monkeypatch.setattr(runner.os, "_exit", lambda code: seen.append(("exit", code)))
    runner.main()
    assert seen == [["-q", "-k", "iq_"], ("exit", 0)]


def test_windows_isolation_runs_only_after_failure_on_experimental_branch():
    from pathlib import Path

    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    diagnostic = workflow.split("\n  windows-crash-isolation:", 1)[1].split(
        "\n  windows-exe:", 1
    )[0]
    assert "needs: windows-tests" in diagnostic
    assert "needs.windows-tests.result == 'failure'" in diagnostic
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in diagnostic
    assert 'selection: "not iq_"' in diagnostic
    assert "selection: iq_" in diagnostic
    assert "ci_windows_pytest.py -k" in diagnostic
    assert "partition: baseline-normal-exit" in diagnostic
    assert "partition: baseline-hard-exit" in diagnostic
    assert "partition: iq-hard-exit" in diagnostic
    assert "PT2VHF_TEST_EXIT_MODE: ${{ matrix.exit_mode }}" in diagnostic
    assert "gh release create" not in diagnostic



def test_normal_shutdown_probe_returns_pytest_status_without_hard_exit(monkeypatch):
    """Opt-in shutdown mode is diagnostic only; never silently hard-exit."""
    import sys
    import types
    import scripts.run_tests as runner

    seen = []
    monkeypatch.setenv("PT2VHF_TEST_EXIT_MODE", "normal")
    monkeypatch.setitem(sys.modules, "pytest", types.SimpleNamespace(
        main=lambda args: seen.append(args) or 5
    ))
    monkeypatch.setattr(sys, "argv", ["run_tests.py", "-k", "not iq_"])

    def forbidden_exit(code):
        raise AssertionError("normal shutdown must not call os._exit")

    monkeypatch.setattr(runner.os, "_exit", forbidden_exit)
    assert runner.main() == 5
    assert seen == [["-q", "-k", "not iq_"]]


def test_invalid_shutdown_probe_mode_fails_closed(monkeypatch):
    import sys
    import types
    import pytest
    import scripts.run_tests as runner

    monkeypatch.setenv("PT2VHF_TEST_EXIT_MODE", "unexpected")
    monkeypatch.setitem(sys.modules, "pytest", types.SimpleNamespace(main=lambda args: 0))
    monkeypatch.setattr(sys, "argv", ["run_tests.py"])
    monkeypatch.setattr(runner.os, "_exit", lambda code: None)
    with pytest.raises(ValueError, match="PT2VHF_TEST_EXIT_MODE"):
        runner.main()
