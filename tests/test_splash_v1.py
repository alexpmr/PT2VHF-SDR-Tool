"""SAT Tool v1.7.2-style welcome splash for next SDR Tool v1.0.

Synthetic QPixmap is used to exercise all behavior without relying on external
network or a physical SDR. Real release still requires the user-supplied JPEG.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar

from pt2vhf.ui import welcome


def _fake_banner(tmp_path: Path) -> Path:
    file = tmp_path / "welcome-banner.jpg"
    image = QPixmap(1200, 675)
    image.fill(Qt.black)
    assert image.save(str(file), "JPG")
    return file


def test_splash_full_banner_and_immediate_close(qt_lifecycle, tmp_path, monkeypatch):
    file = _fake_banner(tmp_path)
    monkeypatch.setattr(welcome, "banner_path", lambda: file)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    inspected = []

    def inspect():
        dlg = QApplication.activeModalWidget()
        assert dlg is not None
        assert dlg.objectName() == "pt2vhfWelcomeDialog"
        banner = dlg.findChild(QLabel, "pt2vhfWelcomeBanner")
        assert banner and not banner.pixmap().isNull()
        pic = banner.pixmap()
        assert pic.width() <= 1200
        assert abs(pic.width() / pic.height() - 1200 / 675) < 0.01
        assert banner.size() == pic.size()
        countdown = dlg.findChild(QLabel, "welcomeCountdown")
        progress = dlg.findChild(QProgressBar, "welcomeProgress")
        assert countdown.text() == "⏱ 10 s"
        assert progress.value() == 10
        assert progress.maximum() == 10
        from PySide6.QtTest import QTest
        QTest.mouseClick(banner, Qt.LeftButton)
        assert opened == ["https://www.pt2vhf.com"]
        dlg.reject()
        inspected.append(True)

    QTimer.singleShot(120, inspect)
    start = time.monotonic()
    result = welcome.show_welcome(None)
    assert result == QDialog.Rejected
    assert inspected and time.monotonic() - start < 2


def test_splash_auto_closes_and_progress_shrinks(qt_lifecycle, tmp_path, monkeypatch):
    file = _fake_banner(tmp_path)
    monkeypatch.setattr(welcome, "banner_path", lambda: file)
    states = []
    def first():
        dlg = QApplication.activeModalWidget()
        assert dlg is not None
        states.append((dlg.findChild(QLabel, "welcomeCountdown").text(),
                       dlg.findChild(QProgressBar, "welcomeProgress").value()))
    QTimer.singleShot(70, first)
    start = time.monotonic()
    result = welcome.show_welcome(None, seconds=1)
    elapsed = time.monotonic() - start
    assert result == QDialog.Accepted
    assert states == [("⏱ 1 s", 1)]
    assert 0.7 <= elapsed < 2.5


def test_existing_startup_schedule_is_preserved():
    src = Path(__file__).resolve().parents[1] / "pt2vhf" / "ui" / "main_window.py"
    text = src.read_text(encoding="utf-8")
    assert 'if not os.environ.get("PT2VHF_NO_STARTUP_DIALOGS"):' in text
    assert "QTimer.singleShot(1800, self._startup_notices)" in text
    assert "self.updates.show_last_result()" in text
    assist = (src.parent / "assist_panels.py").read_text(encoding="utf-8")
    assert "from .welcome import show_welcome as show_splash" in assist


def test_banner_packaging_and_version_ready_for_major_release():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "pt2vhf.spec").read_text(encoding="utf-8")
    assert 'datas.append((banner_path, "pt2vhf/assets/branding"))' in spec
    pkg = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pt2vhf" = ["assets/branding/welcome-banner.jpg"]' in pkg
    assert 'version = "1.0.0"' in pkg
    from pt2vhf import __version__
    assert __version__ == "1.0.0"
