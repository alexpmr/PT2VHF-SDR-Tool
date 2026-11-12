"""Experimental-only Windows Qt shutdown diagnosis, per pytest test case.

The full suite and isolated files have reported native crashes *after* pytest
success. Execute cases from the two suspect UI modules in fresh processes.
Never treat this diagnostic as Windows QA approval or RF validation.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

SUSPECT_FILES = ("tests/test_v010_ui.py", "tests/test_v050_ui.py")
NODE_ID = re.compile(r"^(tests[/\\][^\s:]+\.py::\S+)$")


def parse_case_ids(output: str, files: tuple[str, ...] = SUSPECT_FILES) -> list[str]:
    """Accept only pytest node IDs from the expected modules, not summaries."""
    expected = set(files)
    cases = set()
    for line in output.splitlines():
        match = NODE_ID.fullmatch(line.strip())
        if match:
            case = match.group(1).replace("\\", "/")
            if case.split("::", 1)[0] in expected:
                cases.add(case)
    return sorted(cases)


def probe_cases(timeout_seconds: int = 180, exit_modes: tuple[str, ...] = ("hard", "normal")) -> int:
    if timeout_seconds < 1 or not exit_modes or any(m not in ("hard", "normal") for m in exit_modes):
        raise ValueError("invalid timeout or exit modes")
    collect_cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-k", "not iq_", *SUSPECT_FILES]
    try:
        result = subprocess.run(collect_cmd, capture_output=True, text=True, errors="replace",
                                check=False, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        print("CASE-PROBE collection timeout", file=sys.stderr, flush=True)
        return 2
    if result.returncode:
        print(result.stdout, flush=True)
        print(result.stderr, file=sys.stderr, flush=True)
        print("CASE-PROBE collection failed", file=sys.stderr, flush=True)
        return 2
    cases = parse_case_ids(result.stdout)
    if not cases or set(c.split("::", 1)[0] for c in cases) != set(SUSPECT_FILES):
        print("CASE-PROBE missing cases from one or both suspect modules", file=sys.stderr, flush=True)
        return 2
    failures = []
    print(f"CASE-PROBE {len(cases)} cases x {len(exit_modes)} exit modes", flush=True)
    for mode in exit_modes:
        for case in cases:
            command = [sys.executable, "scripts/ci_windows_pytest.py", "-k", "not iq_", case]
            env = dict(os.environ, PT2VHF_TEST_EXIT_MODE=mode)
            print(f"CASE-PROBE {mode}: {case}", flush=True)
            try:
                run = subprocess.run(command, env=env, capture_output=True, text=True,
                                     errors="replace", check=False, timeout=timeout_seconds)
                if run.returncode:
                    failures.append((mode, case, f"exit={run.returncode}"))
                    print((run.stdout + "\n" + run.stderr)[-4000:], flush=True)
            except subprocess.TimeoutExpired:
                failures.append((mode, case, f"timeout>{timeout_seconds}s"))
    if failures:
        print(f"CASE-PROBE FAILURES {len(failures)}/{len(cases) * len(exit_modes)}:", flush=True)
        for mode, case, status in failures:
            print(f"  {mode} {case}: {status}", flush=True)
        return 1
    print("CASE-PROBE CLEAN (single run only); full Windows QA still blocked", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--exit-mode", choices=("hard", "normal", "both"), default="both")
    args = parser.parse_args(argv)
    modes = ("hard", "normal") if args.exit_mode == "both" else (args.exit_mode,)
    return probe_cases(args.timeout_seconds, modes)


if __name__ == "__main__":
    raise SystemExit(main())
