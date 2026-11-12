"""Experimental Windows exit-mechanism probe; never an application or release workaround.

The prior CI showed 16/16 UI crashes after pytest success at delays 0-2000 ms,
while standalone Qt without pytest passed. Compare ordinary interpreter exit,
CRT-backed os._exit and Win32 TerminateProcess on isolated UI tests.
TerminateProcess deliberately bypasses DLL detach; a clean result is only a
diagnostic clue and MUST NOT be interpreted as Windows QA approval.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from scripts.ci_windows_pytest import is_fatal_runtime_output

SUSPECT_CASES = (
    "tests/test_v010_ui.py::test_main_navigation_and_lcd_band_theme",
    "tests/test_v050_ui.py::test_reconnects_receiver_on_start",
)
MODES = ("hard", "normal", "terminate")

# The diagnostic child is intentionally separate from the production test
# runner. No application code or default pytest shutdown policy is changed.
_TERMINATE_CHILD = """
import ctypes
import sys
import pytest

status = int(pytest.main(["-q", sys.argv[1]]))
sys.stdout.flush()
sys.stderr.flush()
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = ctypes.c_void_p
kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
kernel32.TerminateProcess.restype = ctypes.c_int
if not kernel32.TerminateProcess(kernel32.GetCurrentProcess(), status):
    raise OSError(ctypes.get_last_error(), "TerminateProcess failed")
raise SystemExit(87)  # Must never be reached; treat unexpected return as failure.
"""


def command_for(mode: str, case: str) -> list[str]:
    if mode not in MODES or case not in SUSPECT_CASES:
        raise ValueError("invalid mode or case")
    if mode == "terminate":
        return [sys.executable, "-X", "faulthandler", "-c", _TERMINATE_CHILD, case]
    return [sys.executable, "scripts/ci_windows_pytest.py", case]


def failed_result(returncode: int, output: str) -> bool:
    return returncode != 0 or any(is_fatal_runtime_output(line) for line in output.splitlines())


def probe(timeout_seconds: int = 180, modes: tuple[str, ...] = MODES) -> int:
    if timeout_seconds < 1 or not modes or any(m not in MODES for m in modes):
        raise ValueError("invalid timeout or modes")
    failures = []
    counts = {mode: 0 for mode in modes}
    for mode in modes:
        for case in SUSPECT_CASES:
            env = dict(os.environ, PT2VHF_TEST_EXIT_MODE=mode if mode != "terminate" else "hard",
                       PT2VHF_QT_TEST_TEARDOWN="baseline")
            try:
                run = subprocess.run(command_for(mode, case), capture_output=True,
                                     text=True, errors="replace", check=False,
                                     timeout=timeout_seconds, env=env)
                output = run.stdout + "\n" + run.stderr
                fatal = any(is_fatal_runtime_output(line) for line in output.splitlines())
                failed = failed_result(run.returncode, output)
                detail = f"exit={run.returncode}, fatal={fatal}"
                if failed:
                    print(output[-1800:], flush=True)
            except subprocess.TimeoutExpired:
                failed, detail = True, f"timeout>{timeout_seconds}s"
            if failed:
                counts[mode] += 1
                failures.append((mode, case, detail))
            print(f"EXIT-MECHANISM {mode} {case}: {'FAIL' if failed else 'PASS'} {detail}", flush=True)
    print(f"EXIT-MECHANISM SUMMARY {counts} (diagnostic ONLY; not Windows QA)", flush=True)
    for mode, case, detail in failures:
        print(f"  {mode} {case}: {detail}", flush=True)
    print("EXIT-MECHANISM INTERPRETATION: TerminateProcess bypasses DLL detach; "
          "a clean result would not fix or certify the native crash.", flush=True)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    return probe(args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
