"""One-shot Windows diagnostic: CRT os._exit versus kernel32.TerminateProcess.

This intentionally bypasses Windows DLL detach and CRT process-exit handling.
A clean result here would implicate the shutdown path, NOT prove that Qt/ONNX
or the application is stable. Never use this for production or mandatory QA.
No memory dumps, file uploads, model training, or telemetry are performed.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import runpy
import subprocess
import sys

FATAL_MARKERS = (
    "windows fatal exception:",
    "fatal python error:",
    "segmentation fault",
    "core dumped",
)


def terminate_current_process(code: int) -> None:
    """Exit directly through the Windows kernel, without CRT/DLL teardown."""
    if sys.platform != "win32":
        raise RuntimeError("TerminateProcess probe is Windows-only")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.TerminateProcess.restype = ctypes.c_int
    if not kernel32.TerminateProcess(kernel32.GetCurrentProcess(), int(code)):
        raise OSError(ctypes.get_last_error(), "TerminateProcess failed")
    raise RuntimeError("TerminateProcess unexpectedly returned")


def probe_exit_status(returncode: int, fatal_output: bool) -> int:
    """Fail closed on native fatal markers even if the child returned zero."""
    return returncode if returncode else (86 if fatal_output else 0)


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("This diagnostic must run on Windows")
    if len(sys.argv) == 2 and sys.argv[1] == "--worker":
        # Only this disposable diagnostic subprocess patches os._exit.
        # The mandatory Windows test runner remains entirely unchanged.
        os._exit = terminate_current_process
        sys.argv = [str(Path(__file__).with_name("run_tests.py"))]
        runpy.run_path(sys.argv[0], run_name="__main__")
        raise RuntimeError("Worker returned without terminating")

    command = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), "--worker"]
    fatal = False
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", bufsize=1) as child:
        assert child.stdout is not None
        for line in child.stdout:
            print(line, end="", flush=True)
            fatal |= any(marker in line.casefold() for marker in FATAL_MARKERS)
        returncode = child.wait()
    status = probe_exit_status(returncode, fatal)
    print(f"CI-TERMINATE-PROBE child_exit={returncode} fatal_marker={int(fatal)} "
          f"diagnostic_status={status} not_windows_qa=1", flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
