"""Experimental CI-only native lifecycle census before Windows process exit.

A Python test process can report all assertions passed yet fail inside native
Qt/C runtime while os._exit is invoked. This module logs only aggregate
resource counts, without private data, to determine which resources still
exist at pytest completion. Not a crash fix, not an RF/ONNX validation.
"""
from __future__ import annotations

import os
import sys
import threading


def _win_native_thread_count() -> int | None:
    """Count current process's OS threads, not just Python Thread objects."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        snap_thread = 0x00000004
        invalid_handle_value = ctypes.c_void_p(-1).value

        class THREADENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD),
                ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG),
                ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
        kernel32.Thread32First.restype = wintypes.BOOL
        kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
        kernel32.Thread32Next.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        snap = kernel32.CreateToolhelp32Snapshot(snap_thread, 0)
        if snap is None or snap == invalid_handle_value:
            return None
        try:
            entry = THREADENTRY32()
            entry.dwSize = ctypes.sizeof(entry)
            total = 0
            if kernel32.Thread32First(snap, ctypes.byref(entry)):
                while True:
                    if entry.th32OwnerProcessID == os.getpid():
                        total += 1
                    if not kernel32.Thread32Next(snap, ctypes.byref(entry)):
                        break
            return total
        finally:
            kernel32.CloseHandle(snap)
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def snapshot() -> dict[str, int | None]:
    """Read-only counts; never inspect sensitive memory or send telemetry."""
    threads = threading.enumerate()
    result: dict[str, int | None] = {
        "python_threads": len(threads),
        "python_daemon_threads": sum(bool(t.daemon) for t in threads),
        "native_threads": _win_native_thread_count(),
        "qt_top_level_widgets": None,
        "qt_visible_top_level_widgets": None,
    }
    qt_widgets = sys.modules.get("PySide6.QtWidgets")
    if qt_widgets is not None:
        try:
            app = qt_widgets.QApplication.instance()
            if app is not None:
                widgets = app.topLevelWidgets()
                result["qt_top_level_widgets"] = len(widgets)
                result["qt_visible_top_level_widgets"] = sum(w.isVisible() for w in widgets)
        except (RuntimeError, AttributeError, TypeError):
            pass
    return result


def report(phase: str) -> None:
    """Never fail the suite due to diagnostic instrumentation."""
    try:
        numbers = snapshot()
        fields = " ".join(f"{name}={value if value is not None else 'n/a'}"
                          for name, value in numbers.items())
        print(f"CI-NATIVE-LIFECYCLE phase={phase} {fields}", flush=True)
    except Exception as exc:  # Diagnostic path must never break actual tests.
        print(f"CI-NATIVE-LIFECYCLE unavailable={type(exc).__name__}", flush=True)


def dispose_qt_top_levels() -> tuple[int, int]:
    """Experimental A/B only: request DeferredDelete for leftover Qt widgets.

    Use exclusively after pytest.main() returned and only in a separate
    diagnostic job. This does not belong in user-facing applications or in
    mandatory CI, because forced widget teardown may itself expose a crash.
    Returns (attempted_deletes, failed_requests).
    """
    widgets_module = sys.modules.get("PySide6.QtWidgets")
    core_module = sys.modules.get("PySide6.QtCore")
    if widgets_module is None or core_module is None:
        return 0, 0
    app = widgets_module.QApplication.instance()
    if app is None:
        return 0, 0
    widgets = list(app.topLevelWidgets())
    print(f"CI-QT-DISPOSAL phase=begin widgets={len(widgets)}", flush=True)
    failed = 0
    for widget in widgets:
        try:
            widget.deleteLater()
        except (RuntimeError, AttributeError, TypeError):
            failed += 1
    print(f"CI-QT-DISPOSAL phase=deleteLater-queued failed={failed}", flush=True)
    try:
        core_module.QCoreApplication.sendPostedEvents(
            None, core_module.QEvent.DeferredDelete)
        print("CI-QT-DISPOSAL phase=deferred-events-sent", flush=True)
        app.processEvents()
        print("CI-QT-DISPOSAL phase=events-processed", flush=True)
    except (RuntimeError, AttributeError, TypeError):
        failed += 1
    print(f"CI-QT-DISPOSAL attempted={len(widgets)} failed={failed}",
          flush=True)
    return len(widgets), failed
