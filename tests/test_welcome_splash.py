"""SAT Tool v1.7.2-style welcome splash for PT2VHF SDR Tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QPushButton

from pt2vhf.ui import welcome_splash


def test_splash_banner_is_real_and_scaled_proportionally(qt_lifecycle, monkeypatch, tmp_path):
    """The user-provided seven-product graphic must be present and fit screen."""
    path = welcome_splash.banner_path()
    assert path.is_file(), f"Missing packaged asset: {path}"
    original = QPixmap(str(path))
    assert not original.isNull()
    assert original.width() == 1200
    assert original.height() == 675
    seen = {}

    def inspect_dialog(dlg):
        image = dlg.findChild(QLabel, "welcomeBanner")
        assert image is not None
        pix = image.pixmap()
        assert not pix.isNull()
        screen = dlg.screen() or QApplication.primaryScreen()
        assert pix.width() <= 1200
        if screen:
            assert pix.width() <= int(screen.availableGeometry().width() * 0.88)
        assert abs(pix.width() / pix.height() - original.width() / original.height()) < 0.01
        assert dlg.findChild(QLabel, "welcomeCountdown").text() == "⏱ 10 s"
        assert dlg.findChild(QProgressBar, "welcomeProgress").value() == 10
        seen["ok"] = True
        dlg.reject()

    monkeypatch.setattr(QDialog, "exec", lambda dlg: inspect_dialog(dlg))
    welcome_splash.show_splash(None)
    assert seen.get("ok")


def test_click_banner_opens_official_site(qt_lifecycle, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    banner = welcome_splash.LinkBanner()
    event = SimpleNamespace(
        button=lambda: Qt.MouseButton.LeftButton,
        accept=lambda: None,
    )
    banner.mousePressEvent(event)
    assert opened == ["https://www.pt2vhf.com"]
    banner.close()


def test_automatic_timeout_and_immediate_close(qt_lifecycle, monkeypatch):
    """A one-second test exercises the same countdown logic as ten seconds."""
    result = []

    def fake_exec(dlg):
        label = dlg.findChild(QLabel, "welcomeCountdown")
        button = next(b for b in dlg.findChildren(QPushButton) if b.text() == "Fechar")
        if len(result) == 0:
            result.append(("initial", label.text()))
            QTimer.singleShot(60, button.click)
            dlg.exec_compat_original()
        else:
            dlg.exec_compat_original()
            result.append(("timeout", label.text()))

    # Avoid monkeypatching exec on QDialog: use timer to find the active dialog.
    def click_first():
        dlg = QApplication.activeModalWidget()
        assert isinstance(dlg, QDialog)
        assert dlg.findChild(QLabel, "welcomeCountdown").text() == "⏱ 10 s"
        btn = next(b for b in dlg.findChildren(QPushButton) if b.text() == "Fechar")
        btn.click()

    QTimer.singleShot(40, click_first)
    welcome_splash.show_splash(None, seconds=10)

    seen = []
    def check_tick():
        dlg = QApplication.activeModalWidget()
        assert isinstance(dlg, QDialog)
        label = dlg.findChild(QLabel, "welcomeCountdown")
        seen.append(label.text())
    QTimer.singleShot(20, check_tick)
    welcome_splash.show_splash(None, seconds=1)
    assert seen == ["⏱ 1 s"]
    assert QApplication.activeModalWidget() is None


def test_startup_policy_is_unchanged():
    src = (Path(__file__).resolve().parents[1] / "pt2vhf" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'if not os.environ.get("PT2VHF_NO_STARTUP_DIALOGS"):' in src
    assert "QTimer.singleShot(1800, self._startup_notices)" in src
    assert "show_welcome(self)" in src
    assert "self.updates.show_last_result()" in src
