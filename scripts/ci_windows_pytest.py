"""Run Windows Qt pytest with fail-closed detection of native crash diagnostics.

The existing test runner calls os._exit(pytest_status) to bypass Qt teardown.
On Windows, a native access violation can still be printed by faulthandler
after pytest reports success while the process returns exit code zero.
A green CI job in that situation is not evidence of a clean Windows run.

This wrapper streams all output and rejects fatal diagnostics regardless of
the subprocess exit code. It does not fix the underlying native crash.
"""
from __future__ import annotations

import subprocess
import sys

FATAL_MARKERS = (
    "Windows fatal exception:",
    "Fatal Python error:",
    "Segmentation fault",
    "core dumped",
)


def is_fatal_runtime_output(line: str) -> bool:
    return any(marker.casefold() in line.casefold() for marker in FATAL_MARKERS)


def main() -> int:
    command = [sys.executable, "-X", "faulthandler", "scripts/run_tests.py", *sys.argv[1:]]
    found_fatal = False
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", bufsize=1,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            found_fatal |= is_fatal_runtime_output(line)
        exit_code = process.wait()

    if found_fatal:
        print(
            "ERROR: Native Python/Qt crash diagnostic in test output; "
            "Windows QA must not pass even when pytest reported success.",
            file=sys.stderr,
        )
        return exit_code if exit_code else 86
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
