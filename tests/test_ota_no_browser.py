"""Regression for OTA fallback: detecting an update must never open a browser.

All tests run offline. A legacy (pre-0.13.1) binary cannot be retroactively
patched by this change; its URL whitelist needs a one-time manual update.
"""
import pytest

from pt2vhf import updater


VERSION = "9.9.9"
FILE = "PT2VHF-SDR-Tool-v9.9.9-Win11-x64-Setup.exe"
SITE = "https://www.pt2vhf.com/download.php?product=sdr&file=" + FILE


def manifest(url=SITE, *, sha=None, kind="installer"):
    return {
        "schema": 1,
        "product": "sdr",
        "status": "available",
        "version": VERSION,
        "notes": "Teste de atualização",
        "page": "https://www.pt2vhf.com/sdr",
        "files": [{"name": FILE, "url": url, "kind": kind, "size": 65536,
                   "sha256": sha if sha is not None else "a" * 64}],
    }


def test_site_package_is_selected_with_sha_and_explicit_kind():
    info = updater.select_update(manifest(), "installer", current="0.13.0")
    assert info is not None
    assert info.file is not None
    assert info.file["url"] == SITE
    assert info.unavailable_reason == ""


@pytest.mark.parametrize("payload,expected", [
    (manifest(url="https://untrusted.example/installer.exe"), "URL"),
    (manifest(sha="bad-checksum"), "SHA-256"),
    (manifest(kind="portable"), "não oferece pacote"),
])
def test_unavailable_package_reports_actual_reason(payload, expected):
    info = updater.select_update(payload, "installer", current="0.13.0")
    assert info is not None and info.file is None
    assert expected in info.unavailable_reason


def test_controller_no_browser_on_missing_package(qt_lifecycle, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QPushButton, QWidget, QMessageBox
    from pt2vhf.ui.assist_panels import UpdateController

    parent = QWidget()
    btn = QPushButton(parent)
    controller = UpdateController(parent, btn)
    controller.kind = "installer"

    navigations, warnings, started = [], [], []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: navigations.append(url))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    monkeypatch.setattr(controller, "start", lambda **kw: started.append(kw))
    try:
        missing = updater.select_update(
            manifest("https://untrusted.example/installer.exe"),
            "installer", current="0.13.0")
        controller._on_checked(missing, "", manual=True)
        assert not navigations
        assert not started
        assert warnings and "URL" in warnings[0][-1]
        assert "OTA indisponível" in btn.text()
        assert "URL" in btn.toolTip()

        warnings.clear()
        controller._on_checked(missing, "", manual=False)
        assert not warnings and not navigations and not started

        valid = updater.select_update(manifest(), "installer", current="0.13.0")
        controller._on_checked(valid, "", manual=True)
        assert started == [{"silent": False}]
        assert not navigations
    finally:
        parent.close()


def test_source_mode_cannot_silently_open_site(qt_lifecycle, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QPushButton, QWidget, QMessageBox
    from pt2vhf.ui.assist_panels import UpdateController

    parent = QWidget()
    btn = QPushButton(parent)
    controller = UpdateController(parent, btn)
    controller.kind = "source"
    navigations, notices = [], []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: navigations.append(url))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args))
    try:
        info = updater.select_update(manifest(), "installer", current="0.13.0")
        controller._on_checked(info, "", manual=True)
        assert notices and "código-fonte" in notices[0][-1]
        assert "manual" in btn.text()
        assert navigations == []
    finally:
        parent.close()
