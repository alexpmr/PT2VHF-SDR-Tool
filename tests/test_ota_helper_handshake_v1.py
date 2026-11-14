"""OTA v1.0: helper must ACK startup *before* UI closes.

No remote URL or installer is accessed; native Windows Setup/Portable integration
and hardware shutdown still require their separate real Windows CI jobs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pt2vhf import updater


def _prepare(tmp_path, monkeypatch):
    package = tmp_path / "PT2VHF-SDR-Tool-v1.0.0-Win11-x64-Setup.exe"
    package.write_bytes(b"simulated-verified-exe")
    helper = tmp_path / "original-helper.ps1"
    helper.write_text("# handshake fixture\n", encoding="utf-8")
    monkeypatch.setattr(updater, "helper_script", lambda: helper)
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    return package


def test_acknowledged_helper_launches_and_can_close(tmp_path, monkeypatch):
    pkg = _prepare(tmp_path, monkeypatch)
    captured = []

    class FakeProcess:
        def poll(self):
            return None

    def start(args, **kw):
        captured.append((args, kw))
        ready = Path(args[args.index("-ReadyFile") + 1])
        assert not ready.exists()
        ready.write_text("READY", encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(updater.subprocess, "Popen", start)
    updater.apply(pkg, "installer", "1.0.0")
    assert len(captured) == 1
    args, flags = captured[0]
    assert args[args.index("-WaitPid") + 1].isdigit()
    assert args[args.index("-Mode") + 1] == "Setup"
    assert args[args.index("-Version") + 1] == "1.0.0"
    assert flags["close_fds"] is True
    assert not Path(args[args.index("-ReadyFile") + 1]).exists()


def test_failed_helper_does_not_quit_app(tmp_path, monkeypatch):
    pkg = _prepare(tmp_path, monkeypatch)

    class FakeProcess:
        def poll(self):
            return 1

    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: FakeProcess())
    with pytest.raises(updater.UpdateError, match="PowerShell encerrou"):
        updater.apply(pkg, "installer", "1.0.0")


def test_reject_wrong_helper_ack(tmp_path, monkeypatch):
    pkg = _prepare(tmp_path, monkeypatch)

    class FakeProcess:
        def poll(self):
            return None

    def start(args, **kw):
        Path(args[args.index("-ReadyFile") + 1]).write_text("FAILED", encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(updater.subprocess, "Popen", start)
    with pytest.raises(updater.UpdateError, match="respondeu incorretamente"):
        updater.apply(pkg, "portable", "1.0.0")


def test_launch_failure_is_visible_to_user(tmp_path, monkeypatch):
    pkg = _prepare(tmp_path, monkeypatch)
    def fail(*a, **kw):
        raise OSError("PowerShell launch denied")
    monkeypatch.setattr(updater.subprocess, "Popen", fail)
    with pytest.raises(updater.UpdateError, match="Não foi possível iniciar"):
        updater.apply(pkg, "installer", "1.0.0")


def test_ps_helper_has_ack_and_bounded_wait():
    source = (Path(__file__).resolve().parents[1] /
              "scripts/apply-update.ps1").read_text(encoding="utf-8")
    assert "$ReadyFile" in source
    assert "Set-Content -LiteralPath $ReadyFile -Value 'READY'" in source
    assert "Wait-Exit @($WaitPid) 25" in source
    assert "'/SILENT'" in source and "'/VERYSILENT'" not in source
    assert "PT2VHF-SDR-Tool-ota-helper.log" in source


def test_shutdown_watchdog_is_not_based_on_stopped_qt_timer():
    source = (Path(__file__).resolve().parents[1] /
              "pt2vhf/ui/main_window.py").read_text(encoding="utf-8")
    idx = source.index("    def quit_for_update(self):")
    chunk = source[idx:idx + 900]
    assert "threading.Timer(20.0, lambda: os._exit(0))" in chunk
    assert "QTimer.singleShot(8000" not in chunk


def test_ui_only_closes_after_helper_ack(qt_lifecycle, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget
    from pt2vhf.ui.assist_panels import UpdateController

    parent = QWidget()
    button = QPushButton(parent)
    controller = UpdateController(parent, button)
    called = []
    messages = []
    controller.win.quit_for_update = lambda: called.append("quit")
    monkeypatch.setattr(QMessageBox, "critical",
                        lambda *_args: messages.append(_args[-1]))
    try:
        controller._on_helper_ack("PowerShell failed")
        assert called == []
        assert messages and "PowerShell failed" in messages[0]
        controller._on_helper_ack("")
        assert called == ["quit"]
    finally:
        parent.close()


def test_helper_startup_runs_off_qt_event_loop():
    code = (Path(__file__).resolve().parents[1] /
            "pt2vhf/ui/assist_panels.py").read_text(encoding="utf-8")
    assert "threading.Thread(target=start_helper" in code
    assert "self._helper_ack.emit" in code
    assert "self._helper_ack.connect(self._on_helper_ack)" in code
