"""Espectro + waterfall (pyqtgraph) com sintonia por clique, passband arrastável e marcadores.

Inspirado no KiwiSDR/SDR#/SDR++:
  - clique: sintoniza (arredonda ao passo)    - arrastar o passband: sintoniza
  - arrastar bordas do passband: largura       - roda do mouse: zoom; arrastar com botão direito/meio: pan
  - duplo clique no waterfall: sintoniza e centraliza mantendo zoom
  - duplo clique no espectro: zoom total        - marcadores de memórias e plano de bandas
"""
from __future__ import annotations

import weakref
from collections import deque

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
    centerTuneRequested = Signal(float)  # duplo clique no waterfall: VFO + centro visual
    passbandChanged = Signal(float, float)  # low, high relativos ao VFO (Hz)
    panRequested = Signal(float)            # arrastou para fora da faixa recebida: novo centro (Hz)
    viewChanged = Signal(float, float)      # vista RF atual: centro e largura (Hz), para o zoom FFT

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
        # Raw FFT history is kept at native resolution in float16 (~26 MB for
        # 400 x 32768). Only the on-screen RF span is resampled for the image,
        # so 100 kHz zooms no longer inherit a 2048-bin full-band reduction.
        self._raw_lines = deque(maxlen=self.history)
        self._source_fft_size = 0
        self._view_key = None
        self._image_left_mhz = 0.0
        self._image_right_mhz = 0.0
        self._updating_region = False
        # Zoom FFT: linhas de alta resolução vindas do DDC do engine.
        self._zoom_mode = False
        self._zavg = None
        self._zkey = None
        self._zx = None

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
        # The image buffer is already bounded by pixel width. Qt/pyqtgraph
        # must not apply a second automatic reduction to high-zoom pixels.
        self.img.setAutoDownsample(False)
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
        # Avoid Qt signal -> Python lambda -> self ownership cycles at interpreter shutdown.
        # Keep only a weak reference to the timer owned by this QWidget.
        pan_timer_ref = weakref.ref(self._pan_timer)

        def schedule_pan(*_args):
            timer = pan_timer_ref()
            if timer is not None:
                timer.start(350)

        owner_ref = weakref.ref(self)
        def on_manual_range(*_args):
            owner = owner_ref()
            if owner is not None:
                owner._limit_manual_zoom()
            schedule_pan()

        self.spec.getViewBox().sigRangeChangedManually.connect(on_manual_range)
        self.wf.getViewBox().sigRangeChangedManually.connect(on_manual_range)

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.timeout.connect(self._view_timer)
        redraw_ref = weakref.ref(self._redraw_timer)
        def request_redraw(*_args):
            timer = redraw_ref()
            if timer is not None:
                timer.start(35)
        self.spec.getViewBox().sigXRangeChanged.connect(request_redraw)
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
        data = self._zavg if self._zoom_mode and self._zavg is not None else self._avg
        if data is None:
            return
        floor = float(np.percentile(data, 20))
        top = float(np.percentile(data, 99.8))
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
        if self.fs <= 0 or not np.isfinite(span_hz):
            return
        if span_hz >= self.fs:
            self.reset_zoom()
            return
        span = max(float(span_hz), self.fs / 32768.0)
        lo = self.center - self.fs / 2
        hi = self.center + self.fs / 2
        mid = min(max(self.vfo, lo + span / 2), hi - span / 2)
        self.spec.setXRange((mid - span / 2) / 1e6, (mid + span / 2) / 1e6, padding=0)

    def center_on_vfo(self):
        """Centraliza a vista no VFO sem mostrar RF fora da banda amostrada."""
        view = self.spec.getViewBox().viewRange()[0]
        span = min(self.fs, max((view[1] - view[0]) * 1e6, 10.0))
        if span >= self.fs:
            self.reset_zoom()
            return
        mid = min(max(self.vfo, self.center - (self.fs - span) / 2),
                  self.center + (self.fs - span) / 2)
        self.spec.setXRange((mid - span / 2) / 1e6, (mid + span / 2) / 1e6, padding=0)

    def _limit_manual_zoom(self):
        """Zoom-out via roda do mouse nunca pode mostrar largura RF inventada."""
        if self.fs <= 0 or self._source_fft_size <= 0:
            return
        lo, hi = self.spec.getViewBox().viewRange()[0]
        if (hi - lo) * 1e6 > self.fs * 1.001:
            self.reset_zoom()

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
    MAX_WF_COLS = 2048  # Max display pixels; never truncate the native FFT history.

    def _view_selection(self):
        """Select native FFT bins corresponding to the currently visible RF span.

        The full 32k-point FFT is retained in the history, but only ~1.5x the
        actual viewport width is rendered (up to 2048 columns). At a 100 kHz
        zoom with 2.88 MS/s and FFT 32768, this preserves all ~1138 bins rather
        than downsampling the *entire* receiver band to 2048 first.
        """
        n = self._source_fft_size
        if n <= 0 or self.fs <= 0:
            return None
        lo_mhz, hi_mhz = self.spec.getViewBox().viewRange()[0]
        left = self.center - self.fs / 2
        hz_per_bin = self.fs / n
        start = max(0, min(n - 1, int(np.floor((lo_mhz * 1e6 - left) / hz_per_bin))))
        stop = max(start + 1, min(n, int(np.ceil((hi_mhz * 1e6 - left) / hz_per_bin))))
        if hi_mhz * 1e6 < left or lo_mhz * 1e6 > left + self.fs:
            return None
        plot_width = max(300, float(self.spec.getViewBox().width()))
        screen_cols = min(self.MAX_WF_COLS, max(256, int(plot_width * 1.5)))
        # Com zoom FFT as linhas têm mais bins que a FFT nativa: a imagem
        # acompanha a largura da tela, não o número de bins nativos.
        columns = screen_cols if self._zoom_mode else min(stop - start, screen_cols)
        # Half-bin edges align this image with the native FFT bin centers.
        left_mhz = (left + (start - 0.5) * hz_per_bin) / 1e6
        right_mhz = (left + (stop - 0.5) * hz_per_bin) / 1e6
        key = (self.center, self.fs, n, start, stop, columns, self._zoom_mode)
        return key, start, stop, columns, left_mhz, right_mhz

    def _raster_line(self, values, center, fs, selection):
        """Render one FFT row: native bins on zoom-in, mean power on zoom-out.

        Mean linear power (converted back to dBFS) avoids the artificial
        brightest-bin noise floor of the previous full-band max pooling.
        """
        _key, start, stop, cols, left_mhz, right_mhz = selection
        raw = np.asarray(values, dtype=np.float32)
        if center == self.center and fs == self.fs and len(raw) == self._source_fft_size:
            portion = raw[start:stop]
            if len(portion) == cols:
                return portion.copy()
            if len(portion) < cols:
                # Mais colunas que bins (zoom FFT ligado): repete o bin nativo.
                idx = (np.arange(cols) * len(portion)) // cols
                return portion[idx].astype(np.float32)
            edges = np.linspace(0, len(portion), cols + 1, dtype=np.int32)
            power = np.power(10.0, np.clip(portion, -180.0, 40.0) / 10.0)
            sums = np.add.reduceat(power, edges[:-1])
            mean = sums / np.diff(edges)
            return (10.0 * np.log10(np.maximum(mean, 1e-18))).astype(np.float32)
        # Center was retuned: place older history at its original RF position,
        # not in the new center frequency's coordinates.
        if fs <= 0 or len(raw) == 0:
            return np.full(cols, self.min_db - 10, dtype=np.float32)
        old_left = center - fs / 2
        nraw = len(raw)
        edges_hz = np.linspace(left_mhz * 1e6, right_mhz * 1e6, cols + 1, dtype=np.float64)
        edges = (edges_hz - old_left) * nraw / fs
        if edges[1] - edges[0] >= 1.0:
            # Mais bins que colunas (linha do zoom FFT): potência média por
            # coluna, para não perder portadoras estreitas entre amostras.
            out = np.full(cols, self.min_db - 10, dtype=np.float32)
            inside = (edges[:-1] >= 0) & (edges[1:] <= nraw)
            if inside.any():
                cut = np.clip(np.round(edges).astype(np.int64), 0, nraw)
                first = int(np.argmax(inside))
                last = len(inside) - int(np.argmax(inside[::-1]))
                e = cut[first:last + 1]
                power = np.power(10.0, np.clip(raw[e[0]:e[-1]], -180.0, 40.0) / 10.0)
                sums = np.add.reduceat(power, e[:-1] - e[0])
                widths = np.maximum(np.diff(e), 1)
                out[first:last] = 10.0 * np.log10(np.maximum(sums / widths, 1e-18))
            return out
        targets = np.linspace(left_mhz * 1e6, right_mhz * 1e6, cols,
                              endpoint=False, dtype=np.float64)
        targets += (right_mhz - left_mhz) * 1e6 / max(2 * cols, 1)
        indices = (targets - old_left) * len(raw) / fs
        return np.interp(indices, np.arange(len(raw)), raw,
                         left=self.min_db - 10, right=self.min_db - 10).astype(np.float32)

    def _redraw_history(self):
        """Reraster history after zoom, pan or resize without losing IQ bins."""
        if not self._raw_lines:
            return
        selection = self._view_selection()
        if selection is None:
            self._buf = None
            self._view_key = None
            self.img.clear()
            return
        key, _a, _b, columns, left, right = selection
        if key == self._view_key and self._buf is not None:
            return
        self._view_key = key
        self._image_left_mhz, self._image_right_mhz = left, right
        self._buf = np.full((self.history, columns),
                            self.min_db - 10, dtype=np.float32)
        for idx, (sample, center, fs) in enumerate(self._raw_lines):
            self._buf[idx] = self._raster_line(sample, center, fs, selection)
        self.img.setImage(self._buf, autoLevels=False,
                          levels=(self.min_db, self.max_db))
        self._set_image_rect()

    def _view_timer(self):
        lo, hi = self.spec.getViewBox().viewRange()[0]
        self.viewChanged.emit((lo + hi) / 2 * 1e6, (hi - lo) * 1e6)
        self._redraw_history()

    def _push_row(self, row_values, center, fs):
        """Desloca o waterfall uma linha (ou rerasteriza se a vista mudou)."""
        selection = self._view_selection()
        if selection is None:
            self._buf = None
            self._view_key = None
            self.img.clear()
        elif selection[0] != self._view_key or self._buf is None:
            self._view_key = None
            self._redraw_history()
        else:
            self._buf[1:] = self._buf[:-1]
            self._buf[0] = self._raster_line(row_values, center, fs, selection)
            self.img.setImage(self._buf, autoLevels=False,
                              levels=(self.min_db, self.max_db))

    def add_zoom_line(self, spec_db: np.ndarray, zoom_center: float, zoom_fs: float,
                      center: float, fs: float):
        """Linha de alta resolução (DDC da faixa visível) no lugar da nativa."""
        z = np.asarray(spec_db, dtype=np.float32)
        if len(z) <= 1 or zoom_fs <= 0:
            return
        if fs != self.fs or self._source_fft_size <= 0:
            # Taxa mudou: volta à vista total; o engine retoma as linhas nativas.
            self.reset_zoom()
            return
        if center != self.center:
            self.center = center
            self._buf_center = center
            self._avg = None
            self._peak = None
            self._view_key = None
        self._zoom_mode = True
        self._raw_lines.appendleft((z.astype(np.float16), zoom_center, zoom_fs))
        self._push_row(z, zoom_center, zoom_fs)
        n = len(z)
        key = (zoom_center, zoom_fs, n)
        if self._zavg is None or self._zkey != key:
            self._zavg = z.copy()
            self._zkey = key
            self._zx = (zoom_center + (np.arange(n) - n / 2) * zoom_fs / n) / 1e6
            self._peak = None
        else:
            self._zavg = self.avg_alpha * self._zavg + (1 - self.avg_alpha) * z
        self.curve.setData(self._zx, self._zavg)
        if self.peak_hold:
            self._peak = (self._zavg.copy() if self._peak is None or len(self._peak) != n
                          else np.maximum(self._peak, self._zavg))
            self.peak_curve.setData(self._zx, self._peak)
        self.peak_curve.setVisible(self.peak_hold)

    @property
    def zoom_active(self) -> bool:
        return self._zoom_mode

    def add_line(self, spec_db: np.ndarray, center: float, fs: float):
        full = np.asarray(spec_db, dtype=np.float32)
        if len(full) <= 1 or fs <= 0:
            return
        if self._zoom_mode:
            self._zoom_mode = False
            self._zavg = None
            self._zkey = None
            self._view_key = None
            self._avg = None
            self._peak = None
        span_changed = (fs != self.fs or self._source_fft_size != len(full))
        if span_changed:
            self.fs = fs
            self.center = center
            self._source_fft_size = len(full)
            self._raw_lines.clear()
            self._buf = None
            self._view_key = None
            self._avg = None
            self._peak = None
            self.reset_zoom()
        elif center != self.center:
            vr = self.spec.viewRange()[0]
            self.center = center
            self._buf_center = center
            self._avg = None
            self._peak = None
            self._view_key = None
            if abs(center - (vr[0] + vr[1]) / 2 * 1e6) > fs / 2:
                self.reset_zoom()

        self._raw_lines.appendleft((full.astype(np.float16), center, fs))
        self._push_row(full, center, fs)

        n = len(full)
        if self._avg is None or len(self._avg) != n:
            self._avg = full.copy()
            self._peak = None
        else:
            self._avg = self.avg_alpha * self._avg + (1 - self.avg_alpha) * full
        x = (center + (np.arange(n) - n / 2) * fs / n) / 1e6
        self.curve.setData(x, self._avg)
        if self.peak_hold:
            self._peak = self._avg.copy() if self._peak is None else np.maximum(self._peak, self._avg)
            self.peak_curve.setData(x, self._peak)
        self.peak_curve.setVisible(self.peak_hold)

    def _set_image_rect(self):
        if self._buf is None:
            return
        self.img.setRect(QRectF(self._image_left_mhz, 0,
                               self._image_right_mhz - self._image_left_mhz,
                               self.history))
        self.wf.setYRange(0, self.history, padding=0)

    # ------------------------------------------------------------ eventos
    def _snap(self, hz: float) -> float:
        return round(hz / self.step) * self.step if self.step > 0 else hz

    def _pick_frequency(self, x_mhz: float) -> float | None:
        """Map an on-screen frequency to RF only within an acquired IQ span.

        Never tune to an empty, panned-out region: pyqtgraph can display a
        much wider viewport than the currently acquired receiver bandwidth.
        Keep rounding to the channel step but reject a rounded frequency
        outside the available IQ rather than silently clipping it.
        """
        if (self._buf is None or not np.isfinite(self.center)
                or not np.isfinite(self.fs) or self.fs <= 0
                or not np.isfinite(x_mhz)):
            return None
        hz = float(x_mhz) * 1e6
        left = self.center - self.fs / 2
        right = self.center + self.fs / 2
        if hz < left or hz > right:
            return None
        tuned = self._snap(hz)
        return float(tuned) if left <= tuned <= right else None

    def _clicked(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        for plot in (self.spec, self.wf):
            vb = plot.getViewBox()
            if not vb.sceneBoundingRect().contains(ev.scenePos()):
                continue
            if ev.double() and plot is self.spec:
                # Preserve spectrum double-click gesture: full-width zoom.
                self.reset_zoom()
                return
            pt = vb.mapSceneToView(ev.scenePos())
            target = self._pick_frequency(pt.x())
            if ev.double():
                # Waterfall double-click: selection and centering are atomic at
                # the MainWindow, after VFO/capability checks have passed.
                if target is not None:
                    self.centerTuneRequested.emit(target)
                return
            lo, hi = self.region.getRegion()
            # Spectrum passband is reserved for moving/resizing its handles.
            # In the waterfall itself, any active IQ pixel is clickable.
            if plot is self.spec and lo * 1e6 <= pt.x() * 1e6 <= hi * 1e6:
                return
            if target is not None:
                self.tuneRequested.emit(target)
            return

    def _pan_check(self):
        """Depois de arrastar: limitar o zoom e permitir retune por pan."""
        self._limit_manual_zoom()
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
            target = self._pick_frequency((self.vfo + delta) / 1e6)
            if target is not None:
                self.tuneRequested.emit(target)
            else:
                # A drag beyond the IQ span must not leave the passband
                # visually out of sync with the unchanged receiver VFO.
                self.set_vfo(self.vfo, self.low, self.high)
        else:
            self.passbandChanged.emit(new_low, new_high)

    def eventFilter(self, obj, ev):
        if (obj is self.glw.viewport() and ev.type() == QEvent.Resize
                and hasattr(self, "_redraw_timer")):
            self._redraw_timer.start(40)
        # roda do mouse com Ctrl = sintonia por passos; sem Ctrl = zoom (pyqtgraph)
        if ev.type() == QEvent.Wheel and ev.modifiers() & Qt.ControlModifier:
            steps = 1 if ev.angleDelta().y() > 0 else -1
            self.tuneRequested.emit(self._snap(self.vfo + steps * self.step))
            return True
        return super().eventFilter(obj, ev)
