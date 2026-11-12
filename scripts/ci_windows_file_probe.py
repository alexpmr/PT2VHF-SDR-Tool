"""Diagnostic-only Windows probe: run each non-IQ pytest file in a fresh process.

The full and two-file-shard suites can crash *after* pytest reports success.
Per-file isolation tests whether a single test module reproduces the native
shutdown fault. A clean run is a diagnostic lead, NOT Windows QA approval.
This script never builds installers, trains models, or changes RF behavior.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

from scripts.ci_windows_crash_shard import collected_test_files


def probe_non_iq_files(timeout_seconds: int = 180) -> int:
    """Return nonzero for collection failure, timeout, or any failing file."""
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    collect_cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q",
                   "-k", "not iq_", "tests"]
    try:
        collect = subprocess.run(collect_cmd, capture_output=True, text=True,
                                 errors="replace", check=False,
                                 timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        print("ERROR: non-IQ collection timed out", file=sys.stderr, flush=True)
        return 2
    if collect.returncode:
        print(collect.stdout, flush=True)
        print(collect.stderr, file=sys.stderr, flush=True)
        print("ERROR: non-IQ collection failed", file=sys.stderr, flush=True)
        return 2

    files = collected_test_files(collect.stdout)
    if not files:
        print("ERROR: no non-IQ test files collected", file=sys.stderr, flush=True)
        return 2

    failures: list[tuple[str, str]] = []
    print(f"Probing {len(files)} non-IQ test files individually (hard exit)", flush=True)
    for position, path in enumerate(files, 1):
        print(f"FILE-PROBE {position}/{len(files)}: {path}", flush=True)
        command = [sys.executable, "scripts/ci_windows_pytest.py", "-k", "not iq_", path]
        try:
            result = subprocess.run(command, check=False, timeout=timeout_seconds)
            if result.returncode:
                failures.append((path, f"exit={result.returncode}"))
        except subprocess.TimeoutExpired:
            failures.append((path, f"timeout>{timeout_seconds}s"))

    if failures:
        print(f"FILE-PROBE FAILURES {len(failures)}/{len(files)}:", flush=True)
        for path, status in failures:
            print(f"  {path}: {status}", flush=True)
        return 1
    print(f"FILE-PROBE CLEAN {len(files)}/{len(files)}; full-suite QA still required",
          flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    if args.timeout_seconds < 1:
        parser.error("timeout-seconds must be positive")
    return probe_non_iq_files(args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
