"""SAT Tool-style (v1.9.2 overlay) welcome splash for next SDR Tool v1.0.

Synthetic QPixmap is used to exercise all behavior without relying on external
network or a physical SDR. Real release still requires the user-supplied JPEG.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QPushButton, QWidget

from pt2vhf.ui import welcome


def _fake_banner(tmp_path: Path) -> Path:
    file = tmp_path / "welcome-banner.jpg"
    image = QPixmap(1200, 675)
    image.fill(Qt.black)
    assert image.save(str(file), "JPG")
    return file


def _host():
    host = QWidget()
    host.resize(1000, 700)
    host.show()
    return host


def test_splash_is_sat_tool_overlay_with_full_banner(qt_lifecycle, tmp_path, monkeypatch):
    file = _fake_banner(tmp_path)
    monkeypatch.setattr(welcome, "banner_path", lambda: file)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    host = _host()
    closed = []
    overlay = welcome.show_welcome(host, on_close=lambda: closed.append(True))
    # Same as Sat Tool 1.9.2: a layer inside the main window, not a dialog.
    assert overlay.parent() is host
    assert overlay.objectName() == "welcomeOverlay"
    assert overlay.isVisible() and overlay.geometry() == host.rect()
    assert host.welcome_overlay is overlay
    banner = overlay.findChild(QLabel, "pt2vhfWelcomeBanner")
    assert banner and not banner.pixmap().isNull()
    pic = banner.pixmap()
    dpr = pic.devicePixelRatio()
    assert pic.width() / dpr <= 760
    assert abs(pic.width() / pic.height() - 1200 / 675) < 0.01
    assert overlay.findChild(QLabel, "welcomeCountdown").text() == "⏱ 10 s"
    progress = overlay.findChild(QProgressBar, "welcomeProgress")
    assert progress.value() == 10 and progress.maximum() == 10
    from pt2vhf import __version__
    assert overlay.findChild(QLabel, "pt2vhfWelcomeProduct").text() == f"PT2VHF SDR Tool v{__version__}"
    QTest.mouseClick(banner, Qt.LeftButton)
    assert opened == ["https://www.pt2vhf.com"]
    assert closed == [] and overlay.isVisible()  # clicking the card keeps it open
    host.resize(1200, 800)
    QApplication.processEvents()
    assert overlay.geometry() == host.rect()
    QTest.mouseClick(overlay.findChild(QPushButton, "welcomeClose"), Qt.LeftButton)
    assert closed == [True]
    assert host.welcome_overlay is None and not overlay.isVisible()
    host.close()


def test_splash_closes_on_click_outside_and_esc(qt_lifecycle, tmp_path, monkeypatch):
    file = _fake_banner(tmp_path)
    monkeypatch.setattr(welcome, "banner_path", lambda: file)
    host = _host()
    closed = []
    overlay = welcome.show_welcome(host, on_close=lambda: closed.append("click"))
    QTest.mouseClick(overlay, Qt.LeftButton, pos=overlay.rect().topLeft() + QPoint(3, 3))
    assert closed == ["click"]
    overlay = welcome.show_welcome(host, on_close=lambda: closed.append("esc"))
    overlay.close_welcome()
    overlay.close_welcome()  # idempotent: on_close runs once
    assert closed == ["click", "esc"]
    host.close()


def test_splash_auto_closes_and_progress_shrinks(qt_lifecycle, tmp_path, monkeypatch):
    file = _fake_banner(tmp_path)
    monkeypatch.setattr(welcome, "banner_path", lambda: file)
    host = _host()
    closed = []
    overlay = welcome.show_welcome(host, seconds=1, on_close=lambda: closed.append(time.monotonic()))
    assert overlay.findChild(QLabel, "welcomeCountdown").text() == "⏱ 1 s"
    assert overlay.findChild(QProgressBar, "welcomeProgress").value() == 1
    start = time.monotonic()
    while not closed and time.monotonic() - start < 4:
        QTest.qWait(50)
    assert closed and 0.7 <= closed[0] - start < 2.5
    host.close()


def test_real_banner_is_the_sat_tool_image():
    from PySide6.QtGui import QImageReader
    path = welcome.banner_path()
    assert path.is_file(), "pt2vhf/assets/branding/welcome-banner.jpg must be committed"
    reader = QImageReader(str(path))
    assert bytes(reader.format()) == b"jpeg"
    assert (reader.size().width(), reader.size().height()) == (1200, 675)
    assert path.stat().st_size > 25_000


def test_existing_startup_schedule_is_preserved():
    src = Path(__file__).resolve().parents[1] / "pt2vhf" / "ui" / "main_window.py"
    text = src.read_text(encoding="utf-8")
    assert 'if not os.environ.get("PT2VHF_NO_STARTUP_DIALOGS"):' in text
    assert "QTimer.singleShot(1800, self._startup_notices)" in text
    assert "self.updates.show_last_result()" in text
    assert "show_welcome(self, on_close=" in text
    assist = (src.parent / "assist_panels.py").read_text(encoding="utf-8")
    assert "from .welcome import show_welcome as show_splash" in assist


def test_banner_packaging_and_version_ready_for_major_release():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "pt2vhf.spec").read_text(encoding="utf-8")
    assert 'datas.append((banner_path, "pt2vhf/assets/branding"))' in spec
    pkg = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pt2vhf" = ["assets/branding/welcome-banner.jpg"]' in pkg
    from pt2vhf import __version__
    assert f'version = "{__version__}"' in pkg
    assert __version__.startswith("1.0.")
