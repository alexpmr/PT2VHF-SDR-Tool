"""Display LCD estilo painel de rádio (dígitos de 7 segmentos, S-meter, indicadores).

Interação:
  - roda do mouse sobre um dígito: altera aquele dígito
  - clique na metade superior/inferior de um dígito: +1 / -1
  - digitar números + Enter: entrada direta (MHz, use '.' ou ',' como decimal)
  - setas ←/→: passo de sintonia, ↑/↓: passo x10
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF, QTransform)
from PySide6.QtWidgets import QSizePolicy, QWidget

THEMES = {
    # fundo topo, fundo base, segmento aceso, segmento "fantasma", texto secundário
    "Âmbar": ("#f6b54a", "#d9820f", "#1c1204", "#e0a043", "#3b2405"),
    "Verde": ("#b6e07a", "#7fb444", "#0d1a05", "#a3cf6c", "#1e3a0c"),
    "Azul (negativo)": ("#0b1f3f", "#040b1c", "#a9e4ff", "#11284a", "#5aa6d6"),
    "Noturno": ("#120404", "#050101", "#ff4a2a", "#2a0a06", "#b8341f"),
    "Branco": ("#e9eef0", "#c4ccd0", "#101418", "#d3dade", "#36414a"),
}

# segmentos: a b c d e f g
SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
    "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": "",
    "E": "afged", "r": "eg", "o": "cdeg", "P": "abfge", "L": "fed", "C": "afed",
}


def _segment_polys(w: float, h: float, t: float):
    """Polígonos dos 7 segmentos num retângulo w x h (espessura t)."""
    hh = h / 2
    g = t * 0.18  # folga entre segmentos

    def hseg(y):
        return QPolygonF([QPointF(t / 2 + g, y), QPointF(t + g, y - t / 2), QPointF(w - t - g, y - t / 2),
                          QPointF(w - t / 2 - g, y), QPointF(w - t - g, y + t / 2), QPointF(t + g, y + t / 2)])

    def vseg(x, y0, y1):
        return QPolygonF([QPointF(x, y0 + g), QPointF(x + t / 2, y0 + t / 2 + g), QPointF(x + t / 2, y1 - t / 2 - g),
                          QPointF(x, y1 - g), QPointF(x - t / 2, y1 - t / 2 - g), QPointF(x - t / 2, y0 + t / 2 + g)])

    return {
        "a": hseg(t / 2), "g": hseg(hh), "d": hseg(h - t / 2),
        "f": vseg(t / 2, t / 2, hh), "b": vseg(w - t / 2, t / 2, hh),
        "e": vseg(t / 2, hh, h - t / 2), "c": vseg(w - t / 2, hh, h - t / 2),
    }


class LCDDisplay(QWidget):
    freqChanged = Signal(float)
    stepRequested = Signal(int)  # +1 / -1 passos
    modeClicked = Signal(str)     # tecla de modo no display (inclui "AUTO")
    neighborRequested = Signal(int)  # ◀ -1 / ▶ +1: transmissão vizinha
    autoTuneToggled = Signal()       # tecla A-SINT

    KEYS = ["◀", "AUTO", "NFM", "WFM", "AM", "USB", "LSB", "CW", "DSB", "RAW", "A-SINT", "▶"]

    N_DIGITS = 10  # 4 MHz . 3 kHz . 3 Hz
    DESIGN_WIDTH = 1100.0
    DESIGN_HEIGHT = 255.0
    BAND_RECT = QRectF(668, 51, 266, 90)  # cinco colunas, área marcada pelo usuário

    def __init__(self, parent=None):
        super().__init__(parent)
        # Height-for-width: diminui o painel inteiro, sem barras ou crop.
        self.setMinimumHeight(72)
        self.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.theme = "Âmbar"
        self.freq = 145_570_000
        self.mode = "NFM"
        self.bandwidth = 12000
        self.step = 12500
        self.vfo_name = "VFO A"
        self.mem_label = ""
        self.band_label = ""
        self.signal_dbm = -147.0
        self.signal_valid = False
        self.s_text = "S0"
        self._peak = -147.0
        self._peak_t = 0.0
        self.flags: dict[str, bool] = {}
        self.mode_key = "NFM"      # tecla de modo acesa (o modo real ou "AUTO")
        self.auto_tune = False
        self._key_rects: list[tuple[QRectF, str]] = []
        self.ctcss_text = ""
        self.squelch_open = False
        self._digit_rects: list[tuple[QRectF, int]] = []
        self._hover = -1
        self._entry = ""
        self.min_freq, self.max_freq = 24_000, 1_766_000_000
        self.band_bar = None
        self._last_scale = 1.0

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return max(72, round(width * self.DESIGN_HEIGHT / self.DESIGN_WIDTH))

    def sizeHint(self):
        return QSize(1100, 255)

    def minimumSizeHint(self):
        return QSize(300, 72)

    def _canvas(self):
        scale = min(self.width() / self.DESIGN_WIDTH,
                    self.height() / self.DESIGN_HEIGHT)
        scale = max(0.001, scale)
        left = (self.width() - self.DESIGN_WIDTH * scale) / 2.0
        top = (self.height() - self.DESIGN_HEIGHT * scale) / 2.0
        return scale, left, top

    def _canvas_point(self, pt):
        scale, left, top = self._canvas()
        return QPointF((pt.x() - left) / scale, (pt.y() - top) / scale)

    def attach_band_keys(self, band_bar):
        """Mantém as teclas como widgets clicáveis dentro do contorno LCD."""
        self.band_bar = band_bar
        band_bar.setParent(self)
        band_bar.set_theme(self.theme)
        band_bar.show()
        self._position_band_keys()

    def _position_band_keys(self):
        if self.band_bar is not None:
            scale, left, top = self._canvas()
            rect = self.BAND_RECT
            self.band_bar.setGeometry(
                round(left + rect.x() * scale), round(top + rect.y() * scale),
                max(1, round(rect.width() * scale)), max(1, round(rect.height() * scale)))
            self.band_bar.set_scale(scale)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_band_keys()

    # ---------------------------------------------------------------- dados
    def set_freq(self, f: float):
        self.freq = int(round(f))
        self.update()

    def set_signal(self, dbm: float | None, s_text: str, sq_open: bool):
        """None significa ausência de medição, e não uma barra fixa de ruído."""
        valid = dbm is not None and math.isfinite(float(dbm))
        self.signal_valid = valid
        self.signal_dbm = float(dbm) if valid else -147.0
        self.s_text = s_text if valid else "S--"
        self.squelch_open = bool(sq_open) if valid else False
        now = time.monotonic()
        if not valid:
            self._peak = -147.0
            self._peak_t = now
        elif self.signal_dbm > self._peak or now - self._peak_t > 1.5:
            self._peak, self._peak_t = self.signal_dbm, now
        self.update()

    def set_theme(self, name: str):
        if name in THEMES:
            self.theme = name
            if self.band_bar is not None:
                self.band_bar.set_theme(name)
            self.update()

    # ---------------------------------------------------------------- desenho
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale, left, top = self._canvas()
        p.fillRect(self.rect(), QColor("#1a1d23"))
        p.translate(left, top)
        p.scale(scale, scale)
        bg1, bg2, on, ghost, sub = (QColor(c) for c in THEMES[self.theme])
        r = QRectF(2, 2, self.DESIGN_WIDTH - 4, self.DESIGN_HEIGHT - 4)
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0, bg1)
        grad.setColorAt(1, bg2)
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.fillPath(path, grad)
        p.setPen(QPen(QColor(0, 0, 0, 160), 2))
        p.drawPath(path)

        W, H = r.width(), r.height()
        x0, y0 = r.left() + 14, r.top() + 8
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mono.setBold(True)

        # --- linha superior: indicadores
        mono.setPixelSize(max(11, int(H * 0.085)))
        p.setFont(mono)
        tags = [(self.vfo_name, True), (self.mode, True),
                (f"BW {self._fmt_hz(self.bandwidth)}", True),
                (f"STEP {self._fmt_hz(self.step)}", True)]
        for name in ("AGC", "NB", "NR", "NOTCH", "EQ", "SQL", "TSQ", "SCAN", "VOX", "REC", "REPLAY"):
            tags.append((name, self.flags.get(name, False)))
        x = x0
        for text, active in tags:
            tw = p.fontMetrics().horizontalAdvance(text) + 10
            box = QRectF(x, y0, tw, H * 0.12)
            if active:
                p.setPen(QPen(on, 1.2))
                if text in (self.mode, self.vfo_name) or text in ("REC", "SCAN", "REPLAY"):
                    p.fillRect(box, on)
                    p.setPen(bg1)
                p.drawText(box, Qt.AlignCenter, text)
                if not (text in (self.mode, self.vfo_name) or text in ("REC", "SCAN", "REPLAY")):
                    p.setPen(QPen(on, 1))
                    p.drawRoundedRect(box, 3, 3)
            else:
                p.setPen(ghost)
                p.drawText(box, Qt.AlignCenter, text)
            x += tw + 6
            if x > r.right() - 120:
                break
        # BUSY
        busy = QRectF(r.right() - 82, y0, 70, H * 0.12)
        if self.squelch_open:
            p.fillRect(busy, on)
            p.setPen(bg1)
        else:
            p.setPen(ghost)
        p.drawText(busy, Qt.AlignCenter, "BUSY")

        # --- frequência
        fy = y0 + H * 0.17
        dh = H * 0.34
        dw = dh * 0.52
        small = 0.62
        spacing = dw * 0.28
        txt = f"{self.freq:>10d}"[-10:] if self.entry_active is False else self._entry_digits()
        self._digit_rects = []
        x = x0 + 4
        skew = QTransform().shear(-0.08, 0)
        for i, ch in enumerate(txt):
            place = self.N_DIGITS - 1 - i  # expoente de 10
            sc = small if place < 3 else 1.0
            w, h = dw * sc, dh * sc
            yy = fy + (dh - h)
            rect = QRectF(x, yy, w, h)
            self._digit_rects.append((rect.adjusted(-spacing / 2, -6, spacing / 2, 6), place))
            leading_blank = (ch == " ")
            self._draw_digit(p, rect, ch if not leading_blank else " ", on, ghost, skew)
            if i == self._hover_index() and not self.entry_active:
                p.setPen(QPen(on, 2))
                p.drawLine(QPointF(x, yy + h + 4), QPointF(x + w, yy + h + 4))
            x += w + spacing * sc
            if place in (6, 3):  # pontos separadores
                dot = dw * 0.16
                p.setBrush(on)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QRectF(x - spacing * 0.15, fy + dh - dot, dot, dot))
                x += spacing * 1.1
        freq_right = x
        p.setPen(on)
        mono.setPixelSize(int(H * 0.095))
        p.setFont(mono)
        p.drawText(QRectF(freq_right + 4, fy + dh - H * 0.13, 60, H * 0.13), Qt.AlignLeft, "MHz")

        # --- painel direito: memória / banda / CTCSS / relógio
        rx = 945
        mono.setPixelSize(11)
        p.setFont(mono)
        p.setPen(sub)
        lines = [self.mem_label or "MEM --", self.band_label or "",
                 self.ctcss_text or "",
                 f"{self.s_text} {self.signal_dbm:6.1f} dBm" if self.signal_valid else "S--  -- dBm",
                 time.strftime("%H:%M:%S") + " UTC"]
        lh = H * 0.078
        for k, line in enumerate(lines):
            p.drawText(QRectF(rx, fy - H * 0.035 + k * lh, r.right() - rx - 10, lh),
                       Qt.AlignRight | Qt.AlignVCenter, line)

        # --- S-meter
        self._draw_smeter(p, QRectF(x0, fy + dh + H * 0.05, W - 28, H * 0.19), on, ghost, sub)
        self._draw_keys(p, QRectF(x0, r.bottom() - H * 0.14,
                                  W - 28, H * 0.105), on, ghost, bg1)

        if self.entry_active:
            p.setPen(on)
            mono.setPixelSize(int(H * 0.08))
            p.setFont(mono)
            p.drawText(QRectF(x0, fy - H * 0.01, 300, H * 0.08), Qt.AlignLeft,
                       "ENTRADA DIRETA (MHz) — Enter confirma, Esc cancela")
        p.end()

    def _draw_keys(self, p: QPainter, r: QRectF, on, ghost, bg):
        """Teclas clicáveis do painel: modos, AUTO, auto-sintonia e transmissão vizinha."""
        self._key_rects = []
        f = QFont("Consolas")
        f.setBold(True)
        f.setPixelSize(max(10, int(r.height() * 0.62)))
        p.setFont(f)
        gap = 5.0
        weights = [0.7 if k in ("◀", "▶") else 1.25 if k in ("AUTO", "A-SINT") else 1.0 for k in self.KEYS]
        unit = (r.width() - gap * (len(self.KEYS) - 1)) / sum(weights)
        x = r.left()
        for k, w in zip(self.KEYS, weights):
            box = QRectF(x, r.top(), unit * w, r.height())
            active = (k == self.mode_key) or (k == "A-SINT" and self.auto_tune)
            p.setPen(QPen(on, 1.2))
            if active:
                p.setBrush(on)
                p.drawRoundedRect(box, 4, 4)
                p.setPen(bg)
            else:
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(box, 4, 4)
            p.drawText(box, Qt.AlignCenter, k)
            self._key_rects.append((box, k))
            x += unit * w + gap

    def _draw_digit(self, p: QPainter, rect: QRectF, ch: str, on: QColor, ghost: QColor, skew):
        polys = _segment_polys(rect.width(), rect.height(), rect.width() * 0.2)
        lit = SEGMENTS.get(ch, "")
        p.save()
        p.translate(rect.left() + rect.height() * 0.04, rect.top())
        p.setTransform(skew, True)
        p.setPen(Qt.NoPen)
        for name, poly in polys.items():
            p.setBrush(on if name in lit else ghost)
            p.drawPolygon(poly)
        p.restore()

    def _draw_smeter(self, p: QPainter, r: QRectF, on, ghost, sub):
        # escala: -127 dBm (S0) a -33 dBm (S9+60), S9 = -93 dBm (VHF)
        lo, s9, hi = -147.0, -93.0, -33.0
        nseg = 40
        seg_w = r.width() / nseg
        frac = (min(max(self.signal_dbm, lo), hi) - lo) / (hi - lo)
        lit = int(round(frac * nseg)) if self.signal_valid else 0
        peak = int(round((min(max(self._peak, lo), hi) - lo) / (hi - lo) * nseg)) if self.signal_valid else 0
        bar_h = r.height() * 0.45
        s9_seg = int((s9 - lo) / (hi - lo) * nseg)
        for i in range(nseg):
            rr = QRectF(r.left() + i * seg_w + 1, r.top() + r.height() * 0.42, seg_w - 2,
                        bar_h * (0.55 + 0.45 * i / nseg))
            rr.moveBottom(r.top() + r.height() * 0.42 + bar_h)
            active = i < lit or (peak > 0 and i == peak - 1)
            col = on if active else ghost
            if i >= s9_seg and active:
                col = QColor("#c0161a") if self.theme in ("Âmbar", "Verde", "Branco") else QColor("#ff6060")
            p.fillRect(rr, col)
        f = QFont("Consolas")
        f.setBold(True)
        f.setPixelSize(max(9, int(r.height() * 0.3)))
        p.setFont(f)
        p.setPen(on)
        labels = [("1", -141), ("3", -129), ("5", -117), ("7", -105), ("9", -93),
                  ("+20", -73), ("+40", -53), ("+60", -33)]
        for text, dbm in labels:
            xx = r.left() + (dbm - lo) / (hi - lo) * r.width()
            p.drawText(QRectF(xx - 20, r.top(), 40, r.height() * 0.38), Qt.AlignCenter, text)
        p.drawText(QRectF(r.left() - 12, r.top(), 20, r.height() * 0.38), Qt.AlignCenter, "S")

    @staticmethod
    def _fmt_hz(hz: float) -> str:
        hz = float(hz)
        if hz >= 1e6:
            return f"{hz / 1e6:g}M"
        if hz >= 1000:
            return f"{hz / 1000:g}k"
        return f"{hz:g}"

    # ---------------------------------------------------------------- interação
    @property
    def entry_active(self) -> bool:
        return bool(self._entry)

    def _entry_digits(self) -> str:
        return (self._entry[-10:]).rjust(10)

    def _hover_index(self) -> int:
        return self._hover

    def _place_at(self, pos) -> int | None:
        point = self._canvas_point(pos)
        for i, (rect, place) in enumerate(self._digit_rects):
            if rect.contains(point):
                return place
        return None

    def mouseMoveEvent(self, ev):
        point = self._canvas_point(ev.position())
        over_key = any(rect.contains(point) for rect, _k in self._key_rects)
        self.setCursor(Qt.PointingHandCursor if over_key else Qt.ArrowCursor)
        h = -1
        for i, (rect, _place) in enumerate(self._digit_rects):
            if rect.contains(point):
                h = i
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, _ev):
        self._hover = -1
        self.update()

    def _bump(self, place: int, delta: int):
        f = self.freq + delta * 10 ** place
        f = min(max(f, self.min_freq), self.max_freq)
        if f != self.freq:
            self.freq = f
            self.update()
            self.freqChanged.emit(float(f))

    def wheelEvent(self, ev):
        place = self._place_at(ev.position())
        steps = 1 if ev.angleDelta().y() > 0 else -1
        if place is None:
            self.stepRequested.emit(steps)
        else:
            self._bump(place, steps)
        ev.accept()

    def mousePressEvent(self, ev):
        self.setFocus()
        point = self._canvas_point(ev.position())
        for rect, k in self._key_rects:
            if rect.contains(point):
                if k == "◀":
                    self.neighborRequested.emit(-1)
                elif k == "▶":
                    self.neighborRequested.emit(+1)
                elif k == "A-SINT":
                    self.autoTuneToggled.emit()
                else:
                    self.modeClicked.emit(k)
                return
        for rect, place in self._digit_rects:
            if rect.contains(point):
                up = point.y() < rect.center().y()
                self._bump(place, 1 if up else -1)
                return

    def keyPressEvent(self, ev):
        k = ev.key()
        t = ev.text()
        if t and (t.isdigit() or t in ".,"):
            self._entry += "." if t == "," else t
            self.update()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter) and self._entry:
            try:
                v = float(self._entry)
                if "." not in self._entry and v >= 3000:
                    hz = v * 1e3  # kHz digitado sem decimal
                else:
                    hz = v * 1e6
                if self.min_freq <= hz <= self.max_freq:
                    self.freq = int(hz)
                    self.freqChanged.emit(float(hz))
            except ValueError:
                pass
            self._entry = ""
            self.update()
            return
        if k == Qt.Key_Escape:
            self._entry = ""
            self.update()
            return
        if k == Qt.Key_Backspace and self._entry:
            self._entry = self._entry[:-1]
            self.update()
            return
        if k in (Qt.Key_Right, Qt.Key_Left, Qt.Key_Up, Qt.Key_Down):
            mult = 10 if k in (Qt.Key_Up, Qt.Key_Down) else 1
            sign = 1 if k in (Qt.Key_Right, Qt.Key_Up) else -1
            self.stepRequested.emit(sign * mult)
            return
        super().keyPressEvent(ev)
