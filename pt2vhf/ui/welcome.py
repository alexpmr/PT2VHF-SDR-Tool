"""Official PT2VHF splash, the same one used by PT2VHF Sat Tool (v1.9.2+).

Banner "Powered by www.PT2VHF.com" (the same 1200x675 image shipped by Sat
Tool), clickable, with a link, a 10-second countdown and a Close button.

Like Sat Tool 1.9.2 it is NOT a separate dialog window: it is a layer inside
the main window (dimmed background over the program, card in the centre).
It follows the window when it is moved/resized and closes by itself at the
end of the countdown, or with Fechar / Esc / a click outside the card.

The caller retains the existing 1.8-second startup notice schedule and the
PT2VHF_NO_STARTUP_DIALOGS guard. No network requests, telemetry or updates.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from .. import __version__

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


class _FollowResize(QObject):
    """Keeps the overlay covering the whole host window while it is shown."""

    def __init__(self, host: QWidget, overlay: QWidget):
        super().__init__(overlay)
        self._host = host
        self._overlay = overlay
        host.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._host and event.type() == QEvent.Resize:
            self._overlay.setGeometry(self._host.rect())
        return False

    def detach(self):
        self._host.removeEventFilter(self)


class WelcomeOverlay(QWidget):
    """Non-modal splash layer drawn on top of ``host``."""

    def __init__(self, host: QWidget, *, seconds: int = WELCOME_SECONDS,
                 on_close: Optional[Callable[[], None]] = None):
        super().__init__(host)
        self._host = host
        self._on_close = on_close
        self._closed = False
        self.setObjectName("welcomeOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("#welcomeOverlay{background:rgba(4,10,18,170)}")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        card = QFrame(self)
        card.setObjectName("welcomeCard")
        card.setStyleSheet("#welcomeCard{background:#0f1c2c;border:1px solid #2c4a6b;border-radius:10px}")
        # A click on the card must not reach the dimmed background (which closes).
        card.mousePressEvent = lambda event: event.accept()
        outer.addWidget(card, 0, Qt.AlignCenter)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 10)

        pix = QPixmap(str(banner_path()))
        if not pix.isNull():
            avail = host.width() or 900
            width = max(320, min(760, int(avail * 0.8)))
            dpr = self.devicePixelRatioF()
            pix = pix.scaledToWidth(int(width * dpr), Qt.SmoothTransformation)
            pix.setDevicePixelRatio(dpr)
            banner = _ClickableBanner(card)
            banner.setObjectName("pt2vhfWelcomeBanner")
            banner.setPixmap(pix)
            banner.setCursor(Qt.PointingHandCursor)
            banner.setToolTip("www.PT2VHF.com")
            banner.setAccessibleName("Powered by www.PT2VHF.com")
            layout.addWidget(banner)
        else:  # diagnostic-only fallback if a development install lacks the asset
            title = QLabel("Feito por radioamadores, para radioamadores", card)
            title.setObjectName("pt2vhfWelcomeTitle")
            title.setAccessibleName("Powered by www.PT2VHF.com")
            title.setStyleSheet("font-size:18px;font-weight:700")
            layout.addWidget(title)

        link = QLabel(f'<a href="{OFFICIAL_SITE}" style="color:#6cc7ff;font-weight:700">'
                      'www.PT2VHF.com</a>', card)
        link.setObjectName("pt2vhfWelcomeLink")
        link.setOpenExternalLinks(True)
        product = QLabel(f"PT2VHF SDR Tool v{__version__}", card)
        product.setObjectName("pt2vhfWelcomeProduct")
        product.setStyleSheet("color:#8fa9c4;font-size:11px")
        close = QPushButton("Fechar", card)
        close.setObjectName("welcomeClose")
        countdown = QLabel(card)
        countdown.setObjectName("welcomeCountdown")
        countdown.setStyleSheet("color:#8fa9c4;font-size:11px")
        bar = QProgressBar(card)
        bar.setObjectName("welcomeProgress")
        bar.setRange(0, max(0, seconds))
        bar.setTextVisible(False)
        bar.setFixedSize(90, 4)
        bar.setStyleSheet("QProgressBar{background:#1c3049;border:0;border-radius:2px}"
                          "QProgressBar::chunk{background:#f08a24;border-radius:2px}")
        row = QHBoxLayout()
        row.addWidget(link)
        row.addWidget(product)
        row.addStretch(1)
        row.addWidget(bar)
        row.addWidget(countdown)
        row.addWidget(close)
        layout.addLayout(row)

        self._countdown = countdown
        self._bar = bar
        self._left = max(0, seconds)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        close.clicked.connect(self.close_welcome)
        esc = QShortcut(QKeySequence("Esc"), self)
        esc.activated.connect(self.close_welcome)
        self._follow = _FollowResize(host, self)
        self._close_button = close

    # Click on the dimmed background (outside the card) also closes.
    def mousePressEvent(self, event):
        self.close_welcome()

    def start(self):
        self.setGeometry(self._host.rect())
        self.show()
        self.raise_()
        self._close_button.setFocus()
        self._tick()
        if not self._closed:
            self._timer.start()
        return self

    def _tick(self):
        self._countdown.setText(f"⏱ {self._left} s")
        self._bar.setValue(self._left)
        if self._left <= 0:
            self.close_welcome()
            return
        self._left -= 1

    def close_welcome(self):
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._follow.detach()
        if getattr(self._host, "welcome_overlay", None) is self:
            self._host.welcome_overlay = None
        self.hide()
        self.deleteLater()
        if self._on_close is not None:
            self._on_close()


def show_welcome(parent: QWidget, *, seconds: int = WELCOME_SECONDS,
                 on_close: Optional[Callable[[], None]] = None) -> WelcomeOverlay:
    """Show the Sat Tool-style splash layer over ``parent`` (non-blocking).

    ``on_close`` runs once, after the splash closes (timer, Fechar, Esc or click
    outside), so follow-up startup notices never appear on top of it.
    """
    old = getattr(parent, "welcome_overlay", None)
    if old is not None:
        old.close_welcome()
    overlay = WelcomeOverlay(parent, seconds=seconds, on_close=on_close)
    parent.welcome_overlay = overlay
    return overlay.start()
