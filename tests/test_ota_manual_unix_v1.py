"""Linux/macOS builds must not auto-download/launch Windows .exe updates."""
from __future__ import annotations

import pytest
from pt2vhf import updater


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_frozen_unix_update_is_manual(monkeypatch, platform):
    monkeypatch.setattr(updater.sys, "platform", platform)
    assert updater.install_kind(frozen=True) == "manual"


def test_source_mode_stays_source_on_unix(monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    assert updater.install_kind(frozen=False) == "source"


def test_windows_frozen_modes_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "win32")
    portable = tmp_path / "PT2VHF-SDR-Tool-Portable.exe"
    setup = tmp_path / "PT2VHF-SDR-Tool.exe"
    assert updater.install_kind(portable, frozen=True) == "portable"
    assert updater.install_kind(setup, frozen=True) == "installer"


def test_native_unix_dialog_explains_manual_updates(qt_lifecycle, monkeypatch):
    from PySide6.QtWidgets import QWidget, QPushButton, QMessageBox
    from pt2vhf.ui.assist_panels import UpdateController

    parent = QWidget()
    button = QPushButton(parent)
    controller = UpdateController(parent, button)
    controller.kind = "manual"
    notice = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *_args: notice.append(_args[-1]))
    item = updater.UpdateInfo("1.0.1", "", "", "https://www.pt2vhf.com/sdr",
                              {"name": "invalid-windows-exe"})
    try:
        controller._on_checked(item, "", manual=True)
        assert "manual" in button.text()
        assert notice and "Linux/macOS" in notice[0]
    finally:
        parent.close()
