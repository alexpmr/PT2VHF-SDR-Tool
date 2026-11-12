"""Local crash-log diagnostics: deterministic tests, no native crash required."""
from __future__ import annotations

import io
import sys
import threading

from pt2vhf import crash_diagnostics as diag


def test_local_crash_log_contains_lifecycle_and_exception(tmp_path, monkeypatch):
    captured = []
    old_sys_hook = sys.excepthook
    old_thread_hook = threading.excepthook
    monkeypatch.setattr(diag, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(diag.faulthandler, "enable", lambda **kw: captured.append(kw))
    monkeypatch.setattr(diag, "_handle", None)
    monkeypatch.setattr(diag, "_log_path", None)
    try:
        path = diag.enable()
        assert path == tmp_path / "crash-diagnostics.log"
        assert captured and captured[0]["all_threads"] is True
        assert captured[0]["file"] is diag._handle
        assert path.is_file()
        assert diag.enable() == path  # idempotent; does not reopen file

        try:
            raise RuntimeError("synthetic-crash-example")
        except RuntimeError:
            typ, value, tb = sys.exc_info()
            sys.excepthook(typ, value, tb)
        diag.mark_update_exit()
        diag.mark_qt_quit_requested()
        diag.mark_qt_loop_return(0)
        data = path.read_text(encoding="utf-8")
        assert "START pid=" in data
        assert "UNHANDLED RuntimeError" in data
        assert "synthetic-crash-example" in data
        assert "UPDATE-EXIT requested" in data
        assert "QT-ABOUT-TO-QUIT" in data
        assert "QT-LOOP-RETURN code=0" in data
        assert "CLEAN-EXIT" not in data
    finally:
        sys.excepthook = old_sys_hook
        threading.excepthook = old_thread_hook
        if diag._handle:
            diag._handle.close()
        diag._handle = None
        diag._log_path = None


def test_crash_log_rotation_and_no_startup_failure(tmp_path, monkeypatch):
    path = tmp_path / "crash-diagnostics.log"
    path.write_bytes(b"x" * 256)
    monkeypatch.setattr(diag, "_MAX_BYTES", 100)
    monkeypatch.setattr(diag, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(diag.faulthandler, "enable", lambda **kw: None)
    monkeypatch.setattr(diag, "_handle", None)
    monkeypatch.setattr(diag, "_log_path", None)
    old_sys, old_thread = sys.excepthook, threading.excepthook
    try:
        assert diag.enable() == path
        assert (tmp_path / "crash-diagnostics.log.1").read_bytes() == b"x" * 256
        assert "START" in path.read_text(encoding="utf-8")
    finally:
        sys.excepthook, threading.excepthook = old_sys, old_thread
        if diag._handle:
            diag._handle.close()
        diag._handle = None
        diag._log_path = None


def test_failed_native_handler_does_not_leave_stale_handle(tmp_path, monkeypatch):
    """Native handler setup failure must not block startup or future retries."""
    monkeypatch.setattr(diag, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(diag, "_handle", None)
    monkeypatch.setattr(diag, "_log_path", None)
    old_sys, old_thread = sys.excepthook, threading.excepthook

    def fail_native_handler(**_kwargs):
        raise RuntimeError("synthetic faulthandler failure")

    monkeypatch.setattr(diag.faulthandler, "enable", fail_native_handler)
    try:
        assert diag.enable() is None
        assert diag._handle is None
        assert diag._log_path is None
        # Reattempt is possible and does not reuse a closed file handle.
        assert diag.enable() is None
        assert diag._handle is None
    finally:
        sys.excepthook, threading.excepthook = old_sys, old_thread


def test_qt_lifecycle_markers_do_not_claim_clean_native_exit(monkeypatch):
    """Even app.exec() returning zero cannot certify C++/Qt teardown."""
    output = io.StringIO()
    monkeypatch.setattr(diag, "_handle", output)
    diag.mark_qt_quit_requested()
    diag.mark_qt_loop_return(0)
    diag.mark_qt_loop_return(17)
    data = output.getvalue()
    assert "QT-ABOUT-TO-QUIT" in data
    assert "QT-LOOP-RETURN code=0" in data
    assert "QT-LOOP-RETURN code=17" in data
    assert "native teardown not verified" in data
    assert "CLEAN-EXIT" not in data
