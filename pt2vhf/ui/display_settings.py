"""Configurações visuais com miniaturas reais do display e seleção de bandas."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QRadioButton, QButtonGroup, QVBoxLayout, QWidget)

from .analog import AnalogPanel, STYLES

from ..memory import BAND_PLAN
from .lcd import LCDDisplay, THEMES


class ThemeTile(QFrame):
    selected = Signal(str)

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.theme_name = name
        self.setObjectName("themeTile")
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(5, 5, 5, 5)
        v.setSpacing(3)
        title = QLabel(name)
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)
        preview = LCDDisplay(self)
        preview.set_theme(name)
        preview.set_freq(145.570e6)
        preview.set_signal(-92, "S7", True)
        preview.band_label = "2 m"
        preview.setFixedSize(380, 205)
        preview.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        v.addWidget(preview, alignment=Qt.AlignCenter)
        self.preview = preview

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.selected.emit(self.theme_name)
        super().mousePressEvent(ev)

    def highlight(self, on):
        border = "#f0b44a" if on else "#39444f"
        self.setStyleSheet(f"QFrame#themeTile {{ border: 2px solid {border}; border-radius: 6px; }}")


class DisplaySettings(QWidget):
    bandsChanged = Signal(list)
    analogChanged = Signal(bool, str)

    def __init__(self, cfg, theme_combo, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.theme_combo = theme_combo
        main = QVBoxLayout(self)
        main.setAlignment(Qt.AlignTop)

        themes = QGroupBox("Tema do display — clique na miniatura para aplicar")
        grid = QGridLayout(themes)
        self.tiles = {}
        for idx, name in enumerate(THEMES):
            tile = ThemeTile(name, self)
            tile.selected.connect(self.theme_combo.setCurrentText)
            grid.addWidget(tile, idx // 2, idx % 2, alignment=Qt.AlignLeft)
            self.tiles[name] = tile
        self.theme_combo.currentTextChanged.connect(self.select_theme)
        self.select_theme(self.theme_combo.currentText())
        main.addWidget(themes)

        row = QHBoxLayout()
        row.addWidget(QLabel("Tema:"))
        row.addWidget(self.theme_combo)
        row.addStretch()
        main.addLayout(row)

        group = QGroupBox("Teclas de banda exibidas junto ao display")
        band_grid = QGridLayout(group)
        visible = set(cfg.get("bands_visible", [b.name for b in BAND_PLAN]))
        self.band_checks = {}
        for i, band in enumerate(BAND_PLAN):
            check = QCheckBox(band.name)
            check.setChecked(band.name in visible)
            check.toggled.connect(self._bands_changed)
            band_grid.addWidget(check, i // 5, i % 5)
            self.band_checks[band.name] = check
        main.addWidget(group)

        analog_group = QGroupBox("Instrumentos de ponteiro (S-meter e VU)")
        analog_layout = QVBoxLayout(analog_group)
        self.analog_enable = QCheckBox("Mostrar instrumentos analógicos abaixo do display LCD")
        self.analog_enable.setChecked(bool(cfg.get("analog_enabled", False)))
        analog_layout.addWidget(self.analog_enable)
        previews = QGridLayout()
        self.analog_styles = {}
        self.analog_group = QButtonGroup(self)
        self.analog_group.setExclusive(True)
        current_style = cfg.get("analog_style", "Valvulado")
        for i, style in enumerate(STYLES):
            frame = QFrame()
            col = QVBoxLayout(frame)
            col.setContentsMargins(3, 3, 3, 3)
            radio = QRadioButton(style)
            self.analog_group.addButton(radio)
            radio.setChecked(style == current_style)
            preview = AnalogPanel(style)
            preview.set_readings(-93, 0.3)
            preview.setAttribute(Qt.WA_TransparentForMouseEvents)
            col.addWidget(radio)
            col.addWidget(preview)
            previews.addWidget(frame, i // 2, i % 2)
            self.analog_styles[style] = radio
            radio.toggled.connect(self._analog_changed)
        analog_layout.addLayout(previews)
        self.analog_enable.toggled.connect(self._analog_changed)
        main.addWidget(analog_group)
        main.addStretch()

    def select_theme(self, name):
        for key, tile in self.tiles.items():
            tile.highlight(key == name)

    def _analog_changed(self, *_):
        style = next((s for s, radio in self.analog_styles.items() if radio.isChecked()), "Valvulado")
        self.analogChanged.emit(self.analog_enable.isChecked(), style)

    def _bands_changed(self, *_):
        names = [b.name for b in BAND_PLAN if self.band_checks[b.name].isChecked()]
        self.bandsChanged.emit(names)
