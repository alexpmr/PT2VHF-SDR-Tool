"""Teclas de banda para acesso rápido a recepção SDR."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QToolButton, QWidget, QSizePolicy

from .lcd import THEMES

from ..memory import BAND_PLAN, band_for


class BandKeys(QWidget):
    selected = Signal(object)

    def __init__(self, visible=None, parent=None):
        super().__init__(parent)
        self.bands = [b for b in BAND_PLAN if visible is None or b.name in visible]
        self._theme = "Âmbar"
        self._reasons = {}
        self.buttons = {}
        self._scale = 1.0
        self.visible_names = []
        self.setMinimumSize(0, 0)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background: transparent;")
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(2)
        cols = 5
        for i, band in enumerate(self.bands):
            btn = QToolButton(self)
            btn.setText(band.name.replace(" (PX)", "").replace(" Broadcast", "").replace(" (VHF)", ""))
            btn.setCheckable(True)
            btn.setMinimumSize(0, 0)
            btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            btn.setToolTip(f"{band.name}: {band.start / 1e6:g} a {band.end / 1e6:g} MHz")
            btn.clicked.connect(lambda _checked=False, b=band: self.selected.emit(b))
            grid.addWidget(btn, i // cols, i % cols)
            self.buttons[band.name] = btn
        self._apply_theme()

    def set_scale(self, scale):
        if abs(self._scale - scale) > 0.02:
            self._scale = scale
            self._apply_theme()

    def set_theme(self, name):
        if name in THEMES:
            self._theme = name
            self._apply_theme()

    def _apply_theme(self):
        # Botões incompatíveis são totalmente ocultos; nenhuma tecla falsa é clicável.
        top, _bottom, ink, ghost, _sub = THEMES[self._theme]
        for band in self.bands:
            btn = self.buttons[band.name]
            fg, border, background = ink, ink, top
            btn.setStyleSheet(
                "QToolButton { background: %s; color: %s; border: 1px solid %s; "
                "border-radius: %dpx; font-weight: bold; font-size: %dpx; padding: 0; }"
                "QToolButton:checked { background: %s; color: %s; }"
                "QToolButton:hover { border-width: 2px; }" %
                (background, fg, border, max(1, round(3 * self._scale)),
                 max(4, round(10 * self._scale)),
                 ink, top)
            )

    def refresh(self, vfo, reasons):
        """Remove da grade botões sem suporte e compacta as cinco colunas."""
        current = band_for(vfo)
        self._reasons = dict(reasons)
        available = [b for b in self.bands if not reasons.get(b.name)]
        names = [b.name for b in available]
        if names != self.visible_names:
            grid = self.layout()
            for btn in self.buttons.values():
                grid.removeWidget(btn)
                btn.setEnabled(False)
                btn.hide()
            for i, band in enumerate(available):
                btn = self.buttons[band.name]
                grid.addWidget(btn, i // 5, i % 5)
                btn.setEnabled(True)
                btn.show()
            self.visible_names = names
        for band in self.bands:
            btn = self.buttons[band.name]
            if band.name in names:
                btn.setChecked(current is not None and current.name == band.name)
                btn.setToolTip(f"{band.name}: {band.start / 1e6:g}–{band.end / 1e6:g} MHz")
            else:
                btn.setChecked(False)
                btn.setEnabled(False)
        self._apply_theme()
