"""Privacy-minimized CDB summary for a one-off Windows native crash investigation.

Reads a runner-local CDB log; emits only exception code and module!symbol names
from debugger stack frames. Never prints addresses, memory, paths or raw logs.
A missing exception/stack is NOT evidence that Windows QA passed.
Only explicit exception records count: debugger commands such as `sxe c0000005`
are not crash evidence. Preserve C++ `::` scopes in module!symbol frames.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_FRAME = re.compile(r"^\s*[0-9a-fA-F]{2}\s+.*?\b([A-Za-z0-9_.-]+![A-Za-z0-9_?$@.+<>:-]+)")
_AV = re.compile(
    r"(?im)^\s*(?:access violation\s*-\s*code|exceptioncode\s*:|"
    r"exception_code\s*:\s*(?:\(NTSTATUS\)\s*)?|exception code\s*:)"
    r"\s*(?:0x)?c0000005\b"
)


def summarize(text: str, limit: int = 24) -> tuple[bool, list[str]]:
    """Return whether an access violation was seen and sanitized frame symbols."""
    if limit < 1:
        raise ValueError("limit must be positive")
    # CDB logs may contain earlier, unrelated stacks. An explicit AV marker
    # must precede the frames attributed to it; otherwise fail closed rather
    # than accidentally assigning a prior thread's stack to the AV.
    lines = text.splitlines()
    first_av = next((i for i, line in enumerate(lines) if _AV.search(line)), None)
    found = first_av is not None
    frames: list[str] = []
    for line in lines[first_av + 1:] if found else lines:
        match = _FRAME.search(line)
        if match:
            # CDB often appends a code offset (+0xNN); omit all offsets.
            symbol = re.sub(r"\+0x[0-9a-fA-F]+$", "", match.group(1))
            frames.append(symbol)
            if len(frames) == limit:
                break
    return found, frames


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("CI-NATIVE-STACK status=invalid-arguments")
        return 4
    try:
        # No raw diagnostic content is ever echoed, even on read errors.
        content = Path(args[0]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        print("CI-NATIVE-STACK status=log-unavailable")
        return 4
    found, frames = summarize(content)
    print(f"CI-NATIVE-STACK access_violation={'observed' if found else 'not-observed'} frames={len(frames)}")
    for symbol in frames:
        print(f"CI-NATIVE-STACK frame={symbol}")
    if not found:
        return 2
    if not frames:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
