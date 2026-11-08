"""Teclas de banda para acesso rápido a recepção SDR."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QToolButton, QWidget

from .lcd import THEMES
from PySide6.QtGui import QColor

from ..memory import BAND_PLAN, band_for


class BandKeys(QWidget):
    selected = Signal(object)

    def __init__(self, visible=None, parent=None):
        super().__init__(parent)
        self.bands = [b for b in BAND_PLAN if visible is None or b.name in visible]
        self._theme = "Âmbar"
        self._reasons = {}
        self.buttons = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(2, 1, 2, 1)
        self.setStyleSheet("background: transparent;")
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(2)
        cols = min(12, max(1, (len(self.bands) + 1) // 2))
        for i, band in enumerate(self.bands):
            btn = QToolButton(self)
            btn.setText(band.name.replace(" (PX)", "").replace(" Broadcast", "").replace(" (VHF)", ""))
            btn.setCheckable(True)
            btn.setMinimumHeight(22)
            btn.setMaximumHeight(24)
            btn.setToolTip(f"{band.name}: {band.start / 1e6:g} a {band.end / 1e6:g} MHz")
            btn.clicked.connect(lambda _checked=False, b=band: self.selected.emit(b))
            grid.addWidget(btn, i // cols, i % cols)
            self.buttons[band.name] = btn
        self._apply_theme()

    def set_theme(self, name):
        if name in THEMES:
            self._theme = name
            self._apply_theme()

    def _apply_theme(self):
        # Cor/tom do mesmo tema do LCD, com cinza para bandas não suportadas.
        top, _bottom, ink, ghost, _sub = THEMES[self._theme]
        for band in self.bands:
            btn = self.buttons[band.name]
            disabled = bool(self._reasons.get(band.name))
            fg = "#666666" if disabled else ink
            border = "#686868" if disabled else ink
            background = "#bcbcbc" if disabled else top
            btn.setStyleSheet(
                "QToolButton { background: %s; color: %s; border: 1px solid %s; "
                "border-radius: 3px; font-weight: bold; font-size: 11px; padding: 1px 3px; }"
                "QToolButton:checked { background: %s; color: %s; }"
                "QToolButton:hover { border-width: 2px; }" %
                (background, fg, border, ink if not disabled else "#707070",
                 top if not disabled else "#dddddd")
            )

    def refresh(self, vfo, reasons):
        current = band_for(vfo)
        self._reasons = dict(reasons)
        for band in self.bands:
            btn = self.buttons[band.name]
            reason = reasons.get(band.name, "")
            btn.setChecked(current is not None and current.name == band.name)
            btn.setToolTip(reason or f"{band.name}: {band.start / 1e6:g}–{band.end / 1e6:g} MHz")
        self._apply_theme()
