"""Experimental Windows Qt fixture teardown comparison (never a release gate).

Isolated UI tests crash after reporting success under hard exit, while a
standalone MainWindow without pytest exits cleanly. Compare the existing
session fixture cleanup with a diagnostic-only skipped cleanup, using fresh
processes and fail-closed native-crash detection. Neither outcome homologates
Windows, RF, or ONNX.
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
    "tests/test_v050_ui.py::test_simulator_is_not_reconnected",
    "tests/test_v050_ui.py::test_top_tabs_header_and_levels",
)
MODES = ("baseline", "skip")


def is_failed_run(returncode: int, output: str) -> bool:
    """Never interpret a native fatal diagnostic as success on exit code 0."""
    return returncode != 0 or any(is_fatal_runtime_output(line) for line in output.splitlines())


def probe(timeout_seconds: int = 180, modes: tuple[str, ...] = MODES) -> int:
    if timeout_seconds < 1 or not modes or any(mode not in MODES for mode in modes):
        raise ValueError("invalid timeout or modes")
    failures: list[tuple[str, str, str]] = []
    by_mode: dict[str, int] = {mode: 0 for mode in modes}
    for mode in modes:
        for case in SUSPECT_CASES:
            cmd = [sys.executable, "scripts/ci_windows_pytest.py", "-k", "not iq_", case]
            env = dict(os.environ, PT2VHF_QT_TEST_TEARDOWN=mode, PT2VHF_TEST_EXIT_MODE="hard")
            try:
                run = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                     check=False, timeout=timeout_seconds, env=env)
                output = run.stdout + "\n" + run.stderr
                failed = is_failed_run(run.returncode, output)
                detail = f"exit={run.returncode}, fatal={any(is_fatal_runtime_output(line) for line in output.splitlines())}"
                if failed:
                    print(output[-2200:], flush=True)
            except subprocess.TimeoutExpired:
                failed, detail = True, f"timeout>{timeout_seconds}s"
            if failed:
                failures.append((mode, case, detail))
                by_mode[mode] += 1
            print(f"QT-TEARDOWN {mode} {case}: {'FAIL' if failed else 'PASS'} {detail}", flush=True)
    print(f"QT-TEARDOWN SUMMARY {by_mode} (single-run diagnostic; not a Windows QA pass)", flush=True)
    for mode, case, detail in failures:
        print(f"  {mode} {case}: {detail}", flush=True)
    if len(modes) == 2:
        if by_mode["baseline"] and not by_mode["skip"]:
            print("QT-TEARDOWN HYPOTHESIS: session fixture cleanup implicated; confirm repeatably", flush=True)
        elif by_mode["skip"]:
            print("QT-TEARDOWN HYPOTHESIS: skipping session fixture cleanup is insufficient", flush=True)
        else:
            print("QT-TEARDOWN HYPOTHESIS: not reproduced in this run", flush=True)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    return probe(args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
