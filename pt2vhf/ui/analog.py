"""Instrumentos analógicos vetoriais: S-meter calibrável e VU, sem dependências externas.

As leituras são suavizadas para simular a inércia das agulhas. Desenho somente na
thread GUI; nenhuma interação com hardware ocorre dentro dos paintEvents.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget


STYLES = ("Valvulado", "Militar", "Estúdio")

PALETTES = {
    "Valvulado": ("#f1d9a9", "#291f17", "#382b1c", "#a42d1c", "#333027"),
    "Militar": ("#d9e9d1", "#18251b", "#254331", "#e37431", "#d3dec9"),
    "Estúdio": ("#f1f1ee", "#171a20", "#353c47", "#e1443c", "#f8f8f8"),
}


class NeedleMeter(QWidget):
    """Ponteiro com escala angular e suavização de ataque/retorno."""

    def __init__(self, kind="S", style="Valvulado", parent=None):
        super().__init__(parent)
        if kind not in ("S", "VU"):
            raise ValueError("medidor deve ser S ou VU")
        self.kind = kind
        self.style = style
        self.value = -147.0 if kind == "S" else -60.0
        self.display_value = self.value
        self.peak = self.value
        self.setMinimumSize(145, 95)
        self.setMaximumHeight(125)

    @property
    def limits(self):
        return (-147.0, -33.0) if self.kind == "S" else (-60.0, 0.0)

    @property
    def ticks(self):
        return ([(-141, "1"), (-129, "3"), (-117, "5"), (-105, "7"),
                 (-93, "9"), (-73, "+20"), (-53, "+40"), (-33, "+60")]
                if self.kind == "S" else
                [(-60, "-60"), (-40, "-40"), (-20, "-20"), (-10, "-10"), (0, "0")])

    def set_style(self, style: str):
        if style not in STYLES:
            raise ValueError(f"Estilo desconhecido: {style}")
        self.style = style
        self.update()

    def set_value(self, value: float):
        lo, hi = self.limits
        v = min(max(float(value), lo), hi)
        self.value = v
        # Para 30 Hz de UI, subida ~80 ms e descida ~250 ms.
        k = 0.36 if v >= self.display_value else 0.12
        self.display_value += (v - self.display_value) * k
        if self.display_value > self.peak:
            self.peak = self.display_value
        else:
            self.peak += (self.display_value - self.peak) * 0.035
        self.update()

    def _pt(self, cx, cy, radius, angle):
        a = math.radians(angle)
        return (cx + radius * math.cos(a), cy - radius * math.sin(a))

    def _norm(self, value):
        low, high = self.limits
        return max(0.0, min(1.0, (value - low) / (high - low)))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg, ink, grid, red, text = (QColor(x) for x in PALETTES[self.style])
        w, h = float(self.width()), float(self.height())
        p.setPen(QPen(grid, 1))
        p.setBrush(bg)
        p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)
        cx, cy = w / 2, h * 0.86
        radius = min(w * 0.43, h * 0.66)
        font = QFont("Arial", max(7, int(h * 0.075)))
        font.setBold(True)
        p.setFont(font)
        for value, label in self.ticks:
            angle = 155.0 - self._norm(value) * 130.0
            start = self._pt(cx, cy, radius * 0.82, angle)
            end = self._pt(cx, cy, radius * 0.99, angle)
            p.setPen(QPen(red if self._norm(value) > 0.78 else ink, 2))
            p.drawLine(round(start[0]), round(start[1]), round(end[0]), round(end[1]))
            tx, ty = self._pt(cx, cy, radius * 0.66, angle)
            p.setPen(ink)
            p.drawText(round(tx - 14), round(ty - 7), 28, 15, Qt.AlignCenter, label)
        p.setPen(QPen(ink, 1))
        title = "S-METER  ·  dBm" if self.kind == "S" else "VU  ·  áudio (dBFS)"
        p.drawText(0, 6, int(w), 16, Qt.AlignCenter, title)
        angle = 155.0 - self._norm(self.display_value) * 130.0
        x, y = self._pt(cx, cy, radius * 0.78, angle)
        p.setPen(QPen(red, 2.4))
        p.drawLine(round(cx), round(cy), round(x), round(y))
        p.setPen(QPen(ink, 1))
        p.setBrush(ink)
        p.drawEllipse(round(cx - 4), round(cy - 4), 8, 8)
        p.end()


class AnalogPanel(QWidget):
    """Dois instrumentos independentes com amostras de RF e nível de áudio."""

    def __init__(self, style="Valvulado", parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 1, 2, 1)
        h.setSpacing(4)
        self.s_meter = NeedleMeter("S", style, self)
        self.vu_meter = NeedleMeter("VU", style, self)
        h.addWidget(self.s_meter, 1)
        h.addWidget(self.vu_meter, 1)
        self.setMaximumHeight(130)

    def set_style(self, style):
        self.s_meter.set_style(style)
        self.vu_meter.set_style(style)

    def set_readings(self, dbm: float, audio_level: float):
        self.s_meter.set_value(dbm)
        self.vu_meter.set_value(20.0 * math.log10(max(1e-7, float(audio_level))))
