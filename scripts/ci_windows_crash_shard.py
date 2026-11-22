"""Diagnostic-only Windows pytest sharding for native crash isolation.

Collect the non-IQ tests and split their *files* deterministically across
independent Windows processes. A shard that crashes is a lead, not proof of
which test caused native heap corruption. No installers or RF claims.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


NODE_ID = re.compile(r"^(tests[/\\][^\s:]+\.py)::")


def collected_test_files(output: str) -> list[str]:
    """Extract unique test files from pytest --collect-only -q node IDs."""
    found = set()
    for line in output.splitlines():
        match = NODE_ID.match(line.strip())
        if match:
            found.add(match.group(1).replace("\\", "/"))
    return sorted(found)


def shard_files(files: list[str], index: int, count: int) -> list[str]:
    """Assign whole test files, never individual cases, to stable shards."""
    if count < 1 or not 0 <= index < count:
        raise ValueError("shard index must be in [0, count)")
    return [path for position, path in enumerate(sorted(set(files)))
            if position % count == index]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args(argv)
    if args.count < 1 or not 0 <= args.index < args.count:
        parser.error("invalid shard index/count")

    collect = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-k", "not iq_", "tests"],
        capture_output=True, text=True, errors="replace", check=False,
    )
    if collect.returncode:
        print(collect.stdout, flush=True)
        print(collect.stderr, file=sys.stderr, flush=True)
        print("ERROR: non-IQ pytest collection failed", file=sys.stderr)
        return collect.returncode

    files = collected_test_files(collect.stdout)
    if len(files) < args.count:
        print(f"ERROR: only {len(files)} non-IQ test files for "
              f"{args.count} shards; refusing empty/invalid shard",
              file=sys.stderr)
        return 2

    selected = shard_files(files, args.index, args.count)
    print(f"Windows non-IQ diagnostic shard {args.index + 1}/{args.count}: "
          f"{len(selected)} of {len(files)} test files", flush=True)
    for path in selected:
        print(f"  {path}", flush=True)
    # Keep the original non-IQ -k selection to make this comparable with
    # baseline-hard-exit. The wrapper rejects fatal diagnostics even on rc=0.
    return subprocess.run(
        [sys.executable, "scripts/ci_windows_pytest.py", "-k", "not iq_",
         *selected],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
