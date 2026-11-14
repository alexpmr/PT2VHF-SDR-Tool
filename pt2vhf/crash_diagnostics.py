"""Local crash evidence for packaged SDR executables, with no telemetry.

Creates a small, rotated log under the user's PT2VHF configuration directory.
faulthandler records fatal Python/native signals even when the windowed Windows
binary has no stderr console. Keep the file handle alive for the process life.
"""
from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .config import config_dir

_LOG_NAME = "crash-diagnostics.log"
_MAX_BYTES = 2 * 1024 * 1024
_handle = None
_log_path: Path | None = None


def _write(message: str) -> None:
    if _handle is None:
        return
    try:
        _handle.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
        _handle.flush()
    except (OSError, ValueError):
        pass


def enable() -> Path | None:
    """Install crash hooks before importing Qt; never block normal startup."""
    global _handle, _log_path
    if _handle is not None:
        return _log_path
    try:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / _LOG_NAME
        if path.exists() and path.stat().st_size > _MAX_BYTES:
            rotated = folder / (_LOG_NAME + ".1")
            path.replace(rotated)
        handle = path.open("a", encoding="utf-8", buffering=1)
        _handle, _log_path = handle, path
        _write(f"START pid={os.getpid()} version={sys.version.split()[0]} "
               f"frozen={bool(getattr(sys, 'frozen', False))}")
        faulthandler.enable(file=handle, all_threads=True)
    except (OSError, RuntimeError, ValueError) as ex:
        # faulthandler.enable() can fail after opening the file.  Never keep a
        # stale handle that would make the next enable() look successful.
        if _handle is not None:
            try:
                _handle.close()
            except OSError:
                pass
        _handle, _log_path = None, None
        logging.getLogger(__name__).warning("Crash diagnostics unavailable: %s", ex)
        return None

    previous_hook = sys.excepthook

    def report_unhandled(exc_type, value, tb):
        _write(f"UNHANDLED {getattr(exc_type, '__name__', exc_type)}")
        try:
            traceback.print_exception(exc_type, value, tb, file=handle)
            handle.flush()
        except (OSError, ValueError):
            pass
        if sys.stderr is not None:
            previous_hook(exc_type, value, tb)

    sys.excepthook = report_unhandled

    if hasattr(threading, "excepthook"):
        previous_thread_hook = threading.excepthook

        def report_thread_failure(args):
            _write(f"THREAD-ERROR name={getattr(args.thread, 'name', '?')}")
            report_unhandled(args.exc_type, args.exc_value, args.exc_traceback)
            if sys.stderr is not None:
                previous_thread_hook(args)

        threading.excepthook = report_thread_failure
    return path


def mark_qt_quit_requested() -> None:
    """Qt is about to quit; native teardown can still fail afterward."""
    _write("QT-ABOUT-TO-QUIT (not proof of a clean process exit)")


def mark_qt_loop_return(code: int) -> None:
    """Record the event-loop status without claiming successful native shutdown."""
    _write(f"QT-LOOP-RETURN code={int(code)} (native teardown not verified)")


def mark_update_exit() -> None:
    """Distinguish an intentional OTA shutdown from an unexplained exit."""
    _write("UPDATE-EXIT requested; external installer will restart the app")


def mark_window_close(stage: str, *, ota: bool = False, spontaneous: bool = False) -> None:
    """Trace Qt closeEvent phases without claiming successful process shutdown.

    The spontaneous flag is supplied by Qt and does not establish that a user
    clicked Close; neither it nor the end marker proves native teardown.
    """
    if stage not in {"begin", "engine-stopped", "audio-stopped", "end"}:
        stage = "unknown"
    _write(f"WINDOW-CLOSE stage={stage} ota={int(bool(ota))} "
           f"qt_spontaneous={int(bool(spontaneous))} (native teardown unverified)")
