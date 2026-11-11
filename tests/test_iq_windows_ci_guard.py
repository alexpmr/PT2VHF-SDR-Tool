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
