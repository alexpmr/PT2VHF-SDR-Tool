"""Splash de boas-vindas baseado no PT2VHF Sat Tool v1.7.2.

A regra de exibição pertence à MainWindow; este módulo somente substitui o
conteúdo do diálogo existente. Sem rede, telemetry ou alterações nas preferências.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QProgressBar, QVBoxLayout,
)

OFFICIAL_URL = "https://www.pt2vhf.com"
WELCOME_SECONDS = 10
BANNER_RELATIVE_PATH = Path("assets") / "branding" / "powered-by-pt2vhf.jpg"


def banner_path() -> Path:
    """Works in source, PyInstaller one-dir/one-file on all OSs."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / BANNER_RELATIVE_PATH


class LinkBanner(QLabel):
    """Make the entire banner clickable, not just the footer hyperlink."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcomeBanner")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("www.PT2VHF.com")
        self.setAccessibleName("Powered by www.PT2VHF.com")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(OFFICIAL_URL))
            event.accept()
        else:
            super().mousePressEvent(event)


def show_splash(parent, *, seconds: int = WELCOME_SECONDS) -> None:
    """Modal welcome banner, auto-closed after 10 seconds by default.

    A dialog.exec() preserves the previous startup sequencing:
    MainWindow._startup_notices() displays this first, then the OTA result.
    """
    if seconds < 1:
        raise ValueError("seconds must be positive")

    dlg = QDialog(parent)
    dlg.setObjectName("pt2vhfWelcomeSplash")
    dlg.setWindowTitle("PT2VHF SDR Tool")
    dlg.setStyleSheet(
        "QDialog{background:#081323;color:#e8edf5;}"
        "QLabel{color:#e8edf5;}"
        "QPushButton{background:#183047;border:1px solid #33506c;"
        "border-radius:5px;color:#fff;padding:5px 14px;}"
    )
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 10)
    layout.setSpacing(10)

    source = QPixmap(str(banner_path()))
    if not source.isNull():
        screen = dlg.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        # Keep all seven icons visible and preserve original aspect ratio.
        max_width = min(1200, int(available.width() * 0.88)) if available else 1200
        if available:
            max_height = max(100, int(available.height() * 0.75) - 58)
            max_width = min(max_width, int(max_height * source.width() / source.height()))
        max_width = max(200, max_width)
        scaled = source.scaled(
            max_width, max_width * source.height() // source.width(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        banner = LinkBanner(dlg)
        banner.setPixmap(scaled)
        layout.addWidget(banner, alignment=Qt.AlignmentFlag.AlignHCenter)
    else:
        fallback = QLabel("Powered by www.PT2VHF.com", dlg)
        fallback.setObjectName("welcomeBannerMissing")
        fallback.setStyleSheet("font-size:19px;font-weight:700;color:#f08a24")
        layout.addWidget(fallback)

    link = QLabel(
        f'<a href="{OFFICIAL_URL}" style="color:#6cc7ff;font-weight:700">'
        "www.PT2VHF.com</a>",
        dlg,
    )
    link.setObjectName("welcomeSiteLink")
    link.setOpenExternalLinks(True)
    link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

    buttons = QDialogButtonBox(dlg)
    close = buttons.addButton("Fechar", QDialogButtonBox.ButtonRole.RejectRole)
    close.setDefault(True)
    buttons.rejected.connect(dlg.reject)

    countdown = QLabel(dlg)
    countdown.setObjectName("welcomeCountdown")
    countdown.setStyleSheet("color:#8fa9c4;font-size:11px;")
    bar = QProgressBar(dlg)
    bar.setObjectName("welcomeProgress")
    bar.setRange(0, seconds)
    bar.setTextVisible(False)
    bar.setFixedSize(90, 4)
    bar.setStyleSheet(
        "QProgressBar{background:#1c3049;border:0;border-radius:2px;}"
        "QProgressBar::chunk{background:#f08a24;border-radius:2px;}"
    )
    remaining = {"seconds": seconds}
    timer = QTimer(dlg)
    timer.setInterval(1000)

    def tick():
        remaining["seconds"] -= 1
        left = max(0, remaining["seconds"])
        countdown.setText(f"⏱ {left} s")
        bar.setValue(left)
        if left == 0:
            timer.stop()
            dlg.accept()

    countdown.setText(f"⏱ {seconds} s")
    bar.setValue(seconds)
    timer.timeout.connect(tick)
    dlg.finished.connect(lambda *_: timer.stop())

    row = QHBoxLayout()
    row.addWidget(link)
    row.addStretch(1)
    row.addWidget(bar)
    row.addWidget(countdown)
    row.addWidget(buttons)
    layout.addLayout(row)
    timer.start()
    dlg.exec()
