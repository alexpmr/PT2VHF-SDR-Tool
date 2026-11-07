"""Espectro + waterfall (pyqtgraph) com sintonia por clique, passband arrastável e marcadores.

Inspirado no KiwiSDR/SDR#/SDR++:
  - clique: sintoniza (arredonda ao passo)    - arrastar o passband: sintoniza
  - arrastar bordas do passband: largura       - roda do mouse: zoom; arrastar com botão direito/meio: pan
  - duplo clique: zoom total                   - marcadores de memórias e plano de bandas
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QVBoxLayout, QWidget

pg.setConfigOptions(imageAxisOrder="row-major", antialias=False)

COLORMAPS = {
    "Kiwi": [(0, (0, 0, 0)), (0.15, (0, 0, 80)), (0.35, (0, 60, 200)), (0.55, (0, 200, 220)),
             (0.72, (240, 240, 0)), (0.88, (255, 110, 0)), (1, (255, 0, 0))],
    "SDR#": [(0, (0, 0, 32)), (0.25, (0, 0, 255)), (0.45, (0, 255, 255)), (0.6, (0, 255, 0)),
             (0.8, (255, 255, 0)), (1, (255, 0, 0))],
    "Fósforo": [(0, (0, 8, 0)), (0.5, (0, 140, 30)), (0.85, (120, 255, 120)), (1, (230, 255, 230))],
    "Âmbar": [(0, (10, 4, 0)), (0.5, (150, 70, 0)), (0.85, (255, 170, 40)), (1, (255, 240, 200))],
    "Cinza": [(0, (0, 0, 0)), (1, (255, 255, 255))],
    "Inferno": [(0, (0, 0, 4)), (0.25, (87, 16, 110)), (0.5, (188, 55, 84)), (0.75, (249, 142, 9)),
                (1, (252, 255, 164))],
}


def make_lut(name: str) -> np.ndarray:
    stops = COLORMAPS.get(name, COLORMAPS["Kiwi"])
    cmap = pg.ColorMap([s[0] for s in stops], [s[1] for s in stops])
    return cmap.getLookupTable(0.0, 1.0, 256)


class MHzAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        dec = 3 if spacing >= 1e-3 else 4 if spacing >= 1e-4 else 5
        return [f"{v:.{dec}f}" for v in values]


class SpectrumWaterfall(QWidget):
    tuneRequested = Signal(float)
    passbandChanged = Signal(float, float)  # low, high relativos ao VFO (Hz)
    panRequested = Signal(float)            # arrastou para fora da faixa recebida: novo centro (Hz)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = 400
        self.min_db, self.max_db = -110.0, -40.0
        self.avg_alpha = 0.5
        self.peak_hold = False
        self.step = 12500
        self.center = 145.5e6
        self.fs = 1.2e6
        self.vfo = 145.57e6
        self.low, self.high = -6000.0, 6000.0
        self._avg = None
        self._peak = None
        self._buf = None
        self._buf_center = None
        self._updating_region = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground("#05070c")
        lay.addWidget(self.glw)

        self.spec = self.glw.addPlot(row=0, col=0, axisItems={"bottom": MHzAxis("bottom")})
        self.spec.setMouseEnabled(x=True, y=False)
        self.spec.showGrid(x=True, y=True, alpha=0.18)
        self.spec.setMenuEnabled(False)
        self.spec.hideButtons()
        self.spec.getAxis("left").setWidth(42)
        self.spec.setLabel("left", "dBFS")
        self.curve = self.spec.plot(pen=pg.mkPen("#ffe680", width=1),
                                    fillLevel=-200, brush=pg.mkBrush(70, 140, 255, 70))
        self.curve.setClipToView(True)
        self.curve.setDownsampling(auto=True, method="peak")
        self.peak_curve = self.spec.plot(pen=pg.mkPen((255, 80, 80, 150), width=1))
        self.peak_curve.setVisible(False)

        self.region = pg.LinearRegionItem(brush=pg.mkBrush(255, 255, 255, 40),
                                          pen=pg.mkPen((255, 255, 255, 120)), swapMode="block")
        self.region.setZValue(10)
        self.spec.addItem(self.region)
        self.vfo_line = pg.InfiniteLine(angle=90, pen=pg.mkPen("#ff3030", width=1.5))
        self.spec.addItem(self.vfo_line)
        self.region.sigRegionChangeFinished.connect(self._region_changed)

        self.glw.nextRow()
        self.wf = self.glw.addPlot(row=1, col=0)
        self.wf.setMouseEnabled(x=True, y=False)
        self.wf.setMenuEnabled(False)
        self.wf.hideButtons()
        self.wf.hideAxis("bottom")
        self.wf.getAxis("left").setWidth(42)
        self.wf.getAxis("left").setStyle(showValues=False)
        self.wf.invertY(True)
        self.wf.setXLink(self.spec)
        self.img = pg.ImageItem()
        self.img.setAutoDownsample(True)
        self.wf.addItem(self.img)
        self.wf_vfo = pg.InfiniteLine(angle=90, pen=pg.mkPen((255, 50, 50, 120), width=1))
        self.wf_region = pg.LinearRegionItem(brush=pg.mkBrush(255, 255, 255, 18), pen=pg.mkPen(None),
                                             movable=False)
        self.wf.addItem(self.wf_region)
        self.wf.addItem(self.wf_vfo)
        self.glw.ci.layout.setRowStretchFactor(0, 2)
        self.glw.ci.layout.setRowStretchFactor(1, 3)
        self.set_colormap("Kiwi")

        self._markers: list = []
        self._band_items: list = []
        self.glw.scene().sigMouseClicked.connect(self._clicked)
        from PySide6.QtCore import QTimer
        self._pan_timer = QTimer(self)
        self._pan_timer.setSingleShot(True)
        self._pan_timer.timeout.connect(self._pan_check)
        self.spec.getViewBox().sigRangeChangedManually.connect(lambda *_: self._pan_timer.start(350))
        self.wf.getViewBox().sigRangeChangedManually.connect(lambda *_: self._pan_timer.start(350))
        self.glw.viewport().installEventFilter(self)
        self._apply_levels()

    # ------------------------------------------------------------ configuração
    def set_colormap(self, name: str):
        self.img.setLookupTable(make_lut(name))

    def set_levels(self, min_db: float, max_db: float):
        self.min_db, self.max_db = float(min_db), float(max(max_db, min_db + 5))
        self._apply_levels()

    def _apply_levels(self):
        self.img.setLevels((self.min_db, self.max_db))
        self.spec.setYRange(self.min_db, self.max_db + 5, padding=0)
        if getattr(self, "_marker_data", None):
            self.set_markers(self._marker_data)

    def auto_levels(self):
        if self._avg is None:
            return
        floor = float(np.percentile(self._avg, 20))
        top = float(np.percentile(self._avg, 99.8))
        self.set_levels(floor - 8, max(top + 8, floor + 30))
        return self.min_db, self.max_db

    def set_vfo(self, vfo: float, low: float, high: float):
        self.vfo, self.low, self.high = vfo, low, high
        m = vfo / 1e6
        self.vfo_line.setValue(m)
        self.wf_vfo.setValue(m)
        self._updating_region = True
        self.region.setRegion(((vfo + low) / 1e6, (vfo + high) / 1e6))
        self.wf_region.setRegion(((vfo + low) / 1e6, (vfo + high) / 1e6))
        self._updating_region = False

    def reset_zoom(self):
        self.spec.setXRange((self.center - self.fs / 2) / 1e6, (self.center + self.fs / 2) / 1e6, padding=0)

    def zoom_to_vfo(self, span_hz: float):
        self.spec.setXRange((self.vfo - span_hz / 2) / 1e6, (self.vfo + span_hz / 2) / 1e6, padding=0)

    def clear_peak(self):
        self._peak = None

    def set_markers(self, items: list[tuple[float, str]]):
        """Marcadores de memória: lista de (freq_hz, nome)."""
        for it in self._markers:
            self.spec.removeItem(it)
        self._markers = []
        font = QFont()
        font.setPixelSize(10)
        self._marker_data = sorted(items[:80])
        for k, (f, name) in enumerate(self._marker_data):
            t = pg.TextItem(name, color=(140, 220, 255), anchor=(0.5, 0.0), angle=0)
            t.setFont(font)
            t.setPos(f / 1e6, self.max_db + 5 - (k % 3) * (self.max_db - self.min_db) * 0.07)
            self.spec.addItem(t)
            line = pg.InfiniteLine(f / 1e6, angle=90, pen=pg.mkPen((140, 220, 255, 60), style=Qt.DashLine))
            self.spec.addItem(line)
            self._markers += [t, line]

    def set_extras(self, freqs: list[float]):
        """Linhas verdes nos receptores extras."""
        for it in getattr(self, "_extra_items", []):
            (self.spec if it[1] == 0 else self.wf).removeItem(it[0])
        self._extra_items = []
        for f in freqs:
            for k, plot in enumerate((self.spec, self.wf)):
                ln = pg.InfiniteLine(f / 1e6, angle=90, pen=pg.mkPen((60, 230, 120, 200), width=1.5))
                plot.addItem(ln)
                self._extra_items.append((ln, k))

    def set_bands(self, bands: list[tuple[float, float, str]]):
        for it in self._band_items:
            self.spec.removeItem(it)
        self._band_items = []
        for f0, f1, name in bands:
            reg = pg.LinearRegionItem((f0 / 1e6, f1 / 1e6), movable=False,
                                      brush=pg.mkBrush(80, 200, 120, 14), pen=pg.mkPen((80, 200, 120, 60)))
            reg.setZValue(-10)
            self.spec.addItem(reg)
            self._band_items.append(reg)

    # ------------------------------------------------------------ dados
    MAX_WF_COLS = 2048

    def add_line(self, spec_db: np.ndarray, center: float, fs: float):
        full = spec_db
        if len(spec_db) > self.MAX_WF_COLS:  # reduz por máximo: preserva sinais estreitos
            k = len(spec_db) // self.MAX_WF_COLS
            spec_db = spec_db[:len(spec_db) // k * k].reshape(-1, k).max(axis=1)
        n = len(spec_db)
        span_changed = (fs != self.fs) or (self._buf is None) or (self._buf.shape[1] != n)
        if span_changed:
            self.fs = fs
            self.center = center
            self._buf = np.full((self.history, n), self.min_db - 10, np.float32)
            self._buf_center = center
            self._avg = None
            self._peak = None
            self._rect_dirty = True
            self.reset_zoom()
        elif center != self._buf_center:
            # desloca o histórico ao mudar a frequência central (como no KiwiSDR)
            shift = int(round((center - self._buf_center) / (fs / n)))
            if abs(shift) >= n:
                self._buf[:] = self.min_db - 10
            elif shift > 0:
                self._buf[:, :-shift] = self._buf[:, shift:]
                self._buf[:, -shift:] = self.min_db - 10
            elif shift < 0:
                self._buf[:, -shift:] = self._buf[:, :shift]
                self._buf[:, :-shift] = self.min_db - 10
            self._buf_center = center
            self.center = center
            self._avg = None
            self._peak = None
            self._rect_dirty = True
            vr = self.spec.viewRange()[0]
            d = (center - (vr[0] + vr[1]) / 2 * 1e6)
            if abs(d) > fs / 2:
                self.reset_zoom()

        self._buf[1:] = self._buf[:-1]
        self._buf[0] = spec_db
        self.img.setImage(self._buf, autoLevels=False, levels=(self.min_db, self.max_db))
        if getattr(self, "_rect_dirty", True):
            self._set_image_rect()  # só depois do setImage (escala depende do tamanho da imagem)
            self._rect_dirty = False
        spec_db = full
        n = len(spec_db)
        if self._avg is None or len(self._avg) != n:
            self._avg = spec_db.copy()
            self._peak = None
        else:
            self._avg = self.avg_alpha * self._avg + (1 - self.avg_alpha) * spec_db
        x = (center + (np.arange(n) - n / 2) * fs / n) / 1e6
        self.curve.setData(x, self._avg)
        if self.peak_hold:
            self._peak = self._avg.copy() if self._peak is None else np.maximum(self._peak, self._avg)
            self.peak_curve.setData(x, self._peak)
        self.peak_curve.setVisible(self.peak_hold)

    def _set_image_rect(self):
        n = self._buf.shape[1]
        bin_hz = self.fs / n
        left = (self.center - self.fs / 2 - bin_hz / 2) / 1e6
        self.img.setRect(QRectF(left, 0, self.fs / 1e6, self.history))
        self.wf.setYRange(0, self.history, padding=0)

    # ------------------------------------------------------------ eventos
    def _snap(self, hz: float) -> float:
        return round(hz / self.step) * self.step if self.step > 0 else hz

    def _clicked(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        if ev.double():
            self.reset_zoom()
            return
        for plot in (self.spec, self.wf):
            vb = plot.getViewBox()
            if vb.sceneBoundingRect().contains(ev.scenePos()):
                # clique dentro do passband é tratado pelo arraste da região
                pt = vb.mapSceneToView(ev.scenePos())
                f = pt.x() * 1e6
                lo, hi = self.region.getRegion()
                if plot is self.spec and lo * 1e6 <= f <= hi * 1e6:
                    return
                self.tuneRequested.emit(self._snap(f))
                return

    def _pan_check(self):
        """Depois de arrastar: se a área visível saiu da faixa recebida, pede novo centro."""
        lo, hi = (v * 1e6 for v in self.spec.viewRange()[0])
        vc, span = (lo + hi) / 2, hi - lo
        if span <= 0 or self.fs <= 0:
            return
        outside = lo < self.center - self.fs / 2 or hi > self.center + self.fs / 2
        if outside and abs(vc - self.center) > 0.1 * self.fs and span < self.fs * 1.05:
            self.panRequested.emit(vc)

    def _region_changed(self):
        if self._updating_region:
            return
        a, b = (v * 1e6 for v in self.region.getRegion())
        new_low, new_high = a - self.vfo, b - self.vfo
        width_old = self.high - self.low
        if abs((b - a) - width_old) < 1.0:  # arrastou o passband inteiro -> sintonia
            delta = new_low - self.low
            self.tuneRequested.emit(self._snap(self.vfo + delta))
        else:
            self.passbandChanged.emit(new_low, new_high)

    def eventFilter(self, obj, ev):
        # roda do mouse com Ctrl = sintonia por passos; sem Ctrl = zoom (pyqtgraph)
        if ev.type() == QEvent.Wheel and ev.modifiers() & Qt.ControlModifier:
            steps = 1 if ev.angleDelta().y() > 0 else -1
            self.tuneRequested.emit(self._snap(self.vfo + steps * self.step))
            return True
        return super().eventFilter(obj, ev)
