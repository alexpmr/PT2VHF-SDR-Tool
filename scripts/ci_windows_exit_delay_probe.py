"""Experimental Windows shutdown-timing probe; no installer, no RF certification.

After the Qt fixture teardown A/B test failed in both modes, check whether a
bounded wait between pytest.main() completion and os._exit() changes native
crash reproduction. Each UI case and delay runs in a fresh subprocess.
A delay-dependent result is a lead, NOT a fix or Windows QA approval.
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
DELAYS_MS = (0, 250, 1000, 2000)


def failed_result(returncode: int, output: str) -> bool:
    return returncode != 0 or any(is_fatal_runtime_output(line) for line in output.splitlines())


def probe(timeout_seconds: int = 180, delays_ms: tuple[int, ...] = DELAYS_MS) -> int:
    if timeout_seconds < 1 or not delays_ms or any(delay not in DELAYS_MS for delay in delays_ms):
        raise ValueError("invalid timeout or delay")
    failures = []
    counts = {delay: 0 for delay in delays_ms}
    for delay in delays_ms:
        for case in SUSPECT_CASES:
            cmd = [sys.executable, "scripts/ci_windows_pytest.py", "-k", "not iq_", case]
            env = dict(os.environ, PT2VHF_TEST_EXIT_MODE="hard",
                       PT2VHF_TEST_EXIT_DELAY_MS=str(delay),
                       PT2VHF_QT_TEST_TEARDOWN="baseline")
            try:
                run = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                     check=False, timeout=timeout_seconds, env=env)
                output = run.stdout + "\n" + run.stderr
                fatal = any(is_fatal_runtime_output(line) for line in output.splitlines())
                failed = failed_result(run.returncode, output)
                detail = f"exit={run.returncode}, fatal={fatal}"
                if failed:
                    print(output[-2200:], flush=True)
            except subprocess.TimeoutExpired:
                failed, detail = True, f"timeout>{timeout_seconds}s"
            if failed:
                counts[delay] += 1
                failures.append((delay, case, detail))
            print(f"EXIT-DELAY {delay}ms {case}: {'FAIL' if failed else 'PASS'} {detail}", flush=True)
    print(f"EXIT-DELAY SUMMARY {counts} (single-run diagnostic, NOT Windows QA)", flush=True)
    for delay, case, detail in failures:
        print(f"  {delay}ms {case}: {detail}", flush=True)
    if len(delays_ms) > 1:
        print("EXIT-DELAY INTERPRETATION: timing dependence is a hypothesis only; "
              "reproduce before attributing root cause", flush=True)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    return probe(args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
