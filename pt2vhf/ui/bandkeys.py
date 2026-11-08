"""Teclas de banda para acesso rápido a recepção SDR."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QToolButton, QWidget

from ..memory import BAND_PLAN, band_for


class BandKeys(QWidget):
    selected = Signal(object)

    def __init__(self, visible=None, parent=None):
        super().__init__(parent)
        self.bands = [b for b in BAND_PLAN if visible is None or b.name in visible]
        self.buttons = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(2, 1, 2, 1)
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(2)
        cols = min(9, max(1, (len(self.bands) + 1) // 2))
        for i, band in enumerate(self.bands):
            btn = QToolButton(self)
            btn.setText(band.name.replace(" (PX)", "").replace(" Broadcast", "").replace(" (VHF)", ""))
            btn.setCheckable(True)
            btn.setMinimumHeight(24)
            btn.setToolTip(f"{band.name}: {band.start / 1e6:g} a {band.end / 1e6:g} MHz")
            btn.clicked.connect(lambda _checked=False, b=band: self.selected.emit(b))
            grid.addWidget(btn, i // cols, i % cols)
            self.buttons[band.name] = btn

    def refresh(self, vfo, reasons):
        current = band_for(vfo)
        for band in self.bands:
            btn = self.buttons[band.name]
            reason = reasons.get(band.name, "")
            btn.setChecked(current is not None and current.name == band.name)
            btn.setStyleSheet(
                "QToolButton { color: #777d85; background: #202329; border-color: #30333a; }"
                if reason else ""
            )
            btn.setToolTip(reason or f"{band.name}: {band.start / 1e6:g}–{band.end / 1e6:g} MHz")
