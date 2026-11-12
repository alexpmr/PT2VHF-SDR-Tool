"""Official PT2VHF splash, adapted from PT2VHF Sat Tool v1.7.2.

The caller retains the existing 1.8-second startup notice schedule and the
PT2VHF_NO_STARTUP_DIALOGS guard. No network requests, telemetry or updates.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
                               QLabel, QProgressBar, QVBoxLayout)

WELCOME_SECONDS = 10
OFFICIAL_SITE = "https://www.pt2vhf.com"
BANNER_NAME = "welcome-banner.jpg"


def banner_path() -> Path:
    """Works in source, setuptools installs, and PyInstaller onefile/onedir."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "pt2vhf" / "assets" / "branding" / BANNER_NAME


class _ClickableBanner(QLabel):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(OFFICIAL_SITE))
            event.accept()
        else:
            super().mousePressEvent(event)


def show_welcome(parent, *, seconds: int = WELCOME_SECONDS):
    """Show whole image, scale proportionally, close on timer or button."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("PT2VHF SDR Tool")
    dlg.setObjectName("pt2vhfWelcomeDialog")
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(9)

    image = QPixmap(str(banner_path()))
    if not image.isNull():
        label = _ClickableBanner(dlg)
        label.setObjectName("pt2vhfWelcomeBanner")
        label.setAccessibleName("Powered by www.PT2VHF.com")
        label.setCursor(Qt.PointingHandCursor)
        label.setToolTip("www.PT2VHF.com")
        screen = (parent.screen() if parent is not None else None) or QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else None
        width = min(1200, int(bounds.width() * 0.90)) if bounds else 1200
        height = int(bounds.height() * 0.76) if bounds else 750
        # Keep the ENTIRE supplied 1200 px panorama; never crop either edge.
        scaled = image.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled)
        label.setFixedSize(scaled.size())
        layout.addWidget(label, 0, Qt.AlignCenter)
    else:
        # Diagnostic-only fallback if an external/development install lacks asset.
        missing = QLabel("Powered by www.PT2VHF.com", dlg)
        missing.setAccessibleName("Powered by www.PT2VHF.com")
        missing.setStyleSheet("color:#ff982c;font-size:22px;font-weight:bold")
        layout.addWidget(missing)

    link = QLabel(f'<a href="{OFFICIAL_SITE}" style="color:#6cc7ff;font-weight:700">'
                  'www.PT2VHF.com</a>', dlg)
    link.setObjectName("pt2vhfWelcomeLink")
    link.setOpenExternalLinks(True)

    countdown = QLabel(dlg)
    countdown.setObjectName("welcomeCountdown")
    countdown.setStyleSheet("color:#9cb0c5;font-size:11px")
    bar = QProgressBar(dlg)
    bar.setObjectName("welcomeProgress")
    bar.setRange(0, seconds)
    bar.setTextVisible(False)
    bar.setFixedSize(90, 4)
    bar.setStyleSheet("QProgressBar{background:#1c3049;border:0;border-radius:2px}"
                      "QProgressBar::chunk{background:#f08a24;border-radius:2px}")

    controls = QDialogButtonBox(dlg)
    close = controls.addButton("Fechar", QDialogButtonBox.RejectRole)
    close.setDefault(True)
    controls.rejected.connect(dlg.reject)

    row = QHBoxLayout()
    row.addWidget(link)
    row.addStretch(1)
    row.addWidget(bar)
    row.addWidget(countdown)
    row.addWidget(controls)
    layout.addLayout(row)

    remaining = {"seconds": seconds}
    timer = QTimer(dlg)
    timer.setInterval(1000)

    def tick():
        countdown.setText(f"⏱ {remaining['seconds']} s")
        bar.setValue(remaining["seconds"])
        if remaining["seconds"] <= 0:
            timer.stop()
            dlg.accept()
        else:
            remaining["seconds"] -= 1

    timer.timeout.connect(tick)
    dlg.finished.connect(lambda *_: timer.stop())
    tick()
    if seconds > 0:
        timer.start()
    # Modal as in Sat Tool 1.7.2; parent prevents parallel startup popups.
    return dlg.exec()
