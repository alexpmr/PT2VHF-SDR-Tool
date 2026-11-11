"""Local crash-log diagnostics: deterministic tests, no native crash required."""
from __future__ import annotations

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
        diag.mark_clean_exit()
        data = path.read_text(encoding="utf-8")
        assert "START pid=" in data
        assert "UNHANDLED RuntimeError" in data
        assert "synthetic-crash-example" in data
        assert "CLEAN-EXIT" in data
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
