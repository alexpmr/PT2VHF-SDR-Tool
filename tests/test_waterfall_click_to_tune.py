"""Waterfall click-to-tune regression tests; Qt offscreen and synthetic FFT only."""
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from pt2vhf.ui.waterfall import SpectrumWaterfall


def _ui(qt_lifecycle):
    w = SpectrumWaterfall()
    w.step = 12_500
    w.set_vfo(145_500_000, -6_000, 6_000)
    w.show()
    QApplication.processEvents()
    return w


def _click(w, plot, hz, y=None, double=False):
    # Spectrum uses negative dBFS; waterfall uses history-row indices.
    if y is None:
        y = -75 if plot is w.spec else 100
    view = plot.getViewBox()
    scene_point = view.mapViewToScene(QPointF(hz / 1e6, y))
    assert view.sceneBoundingRect().contains(scene_point)
    event = SimpleNamespace(button=lambda: Qt.LeftButton, double=lambda: double,
                            scenePos=lambda: scene_point)
    w._clicked(event)


def test_tune_by_click_ignores_missing_iq_and_invalid_values(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        assert w._pick_frequency(145.5) is None
        assert w._pick_frequency(float("nan")) is None
        assert w._pick_frequency(float("inf")) is None
    finally:
        w.close()


def test_waterfall_panned_beyond_iq_range_does_not_tune(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -85.0, dtype=np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.2, 145.8, padding=0)  # wider than IQ: 145.4–145.6
        QApplication.processEvents()
        received = []
        w.tuneRequested.connect(received.append)
        _click(w, w.wf, 145_525_100)  # waterfall, valid RF IQ
        assert received == [145_525_000]
        _click(w, w.wf, 145_350_000)  # panned empty region
        _click(w, w.wf, 145_650_000)
        assert received == [145_525_000]
        assert w._pick_frequency(145.399) is None
        assert w._pick_frequency(145.601) is None
    finally:
        w.close()


def test_waterfall_inside_passband_remains_clickable(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90.0, dtype=np.float32), 145_500_000, 200_000)
        QApplication.processEvents()
        heard = []
        w.tuneRequested.connect(heard.append)
        _click(w, w.spec, 145_500_000)  # spectrum passband belongs to region drag
        assert heard == []
        _click(w, w.wf, 145_500_000)  # waterfall should tune at the same RF frequency
        assert heard == [145_500_000]
    finally:
        w.close()


def test_frequency_snap_outside_acquired_edge_is_rejected(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90.0, dtype=np.float32), 145_500_000, 208_000)
        # 145.396–145.604 MHz: 145.603 MHz would snap to 145.600, acceptable.
        assert w._pick_frequency(145.603) == 145_600_000
        # A step coarser than the sampled bandwidth must not push VFO outside IQ.
        w.step = 30_000
        w.center = 145_515_000
        w.fs = 20_000
        assert w._pick_frequency(145.516) is None
        w.step = 1_000
        assert w._pick_frequency(145.516) == 145_516_000
    finally:
        w.close()


def test_drag_passband_outside_acquired_iq_restores_vfo(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -85.0, dtype=np.float32), 145_500_000, 200_000)
        heard = []
        w.tuneRequested.connect(heard.append)
        w.region.setRegion((145.615, 145.627))  # same 12 kHz width, but beyond RF
        QApplication.processEvents()
        assert heard == []
        lo, hi = w.region.getRegion()
        assert abs(lo - 145.494) < 0.00001
        assert abs(hi - 145.506) < 0.00001
    finally:
        w.close()


def test_double_click_waterfall_tunes_and_centers_without_losing_zoom(qt_lifecycle):
    """The MainWindow receives RF frequency, updates VFO/LCD and then centers."""
    from pt2vhf.ui.main_window import MainWindow

    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90, np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.46, 145.54, padding=0)
        QApplication.processEvents()
        initial_range = w.spec.viewRange()[0]
        initial_span = initial_range[1] - initial_range[0]

        class ReceiverHarness:
            def __init__(self):
                self.wf = w
                self.calls = []
                self.lcd_freq = None

            def tune(self, freq):
                self.calls.append(("tune", freq))
                self.lcd_freq = freq
                self.wf.set_vfo(freq, -6000, 6000)

            def _after_select(self):
                self.calls.append(("auto", None))

        harness = ReceiverHarness()
        single_clicks = []
        w.tuneRequested.connect(single_clicks.append)
        w.centerTuneRequested.connect(
            lambda freq: MainWindow.select_transmission_centered(harness, freq))
        _click(w, w.wf, 145_525_100, double=True)

        assert harness.calls == [("tune", 145_525_000), ("auto", None)]
        assert harness.lcd_freq == 145_525_000
        assert w.vfo == 145_525_000
        assert single_clicks == []  # No duplicate "simple click" from double-click signal.
        centered = w.spec.viewRange()[0]
        assert abs((centered[0] + centered[1]) / 2 - 145.525) < 1e-5
        assert abs((centered[1] - centered[0]) - initial_span) < 1e-5
        assert abs(w.wf.getViewBox().viewRange()[0][0] - centered[0]) < 1e-5
    finally:
        w.close()


def test_double_click_outside_acquired_iq_does_nothing(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90, np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.2, 145.8, padding=0)
        QApplication.processEvents()
        before = w.spec.viewRange()[0]
        requested, centered = [], []
        w.tuneRequested.connect(requested.append)
        w.centerTuneRequested.connect(centered.append)

        _click(w, w.wf, 145_350_000, double=True)
        _click(w, w.wf, 145_650_000, double=True)
        assert requested == centered == []
        assert w.spec.viewRange()[0] == before
        assert w.vfo == 145_500_000
    finally:
        w.close()


def test_double_click_over_spectrum_keeps_zoom_reset_behavior(qt_lifecycle):
    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90, np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.46, 145.54, padding=0)
        QApplication.processEvents()
        centered, single = [], []
        w.centerTuneRequested.connect(centered.append)
        w.tuneRequested.connect(single.append)

        _click(w, w.spec, 145_520_000, double=True)
        assert centered == single == []
        view = w.spec.viewRange()[0]
        assert abs(view[0] - 145.4) < 1e-5
        assert abs(view[1] - 145.6) < 1e-5
    finally:
        w.close()


def test_double_click_never_recenters_after_tune_rejection(qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow

    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90, np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.46, 145.54, padding=0)
        QApplication.processEvents()
        before = list(w.spec.viewRange()[0])

        class RejectingReceiver:
            wf = w
            def __init__(self):
                self.calls = []
            def tune(self, freq):
                self.calls.append(("rejected", freq))
                return False
            def _after_select(self):
                self.calls.append(("unexpected", None))

        receiver = RejectingReceiver()
        w.centerTuneRequested.connect(
            lambda freq: MainWindow.select_transmission_centered(receiver, freq))
        _click(w, w.wf, 145_525_000, double=True)
        assert receiver.calls == [("rejected", 145_525_000)]
        assert list(w.spec.viewRange()[0]) == before
        assert w.vfo == 145_500_000
    finally:
        w.close()


def test_real_qt_double_click_reaches_waterfall_handler(qt_lifecycle):
    """Send an actual Qt double-click to the graphics viewport, not a fake event."""
    from PySide6.QtTest import QTest

    w = _ui(qt_lifecycle)
    try:
        w.add_line(np.full(512, -90, np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.46, 145.54, padding=0)
        QApplication.processEvents()
        heard = []
        w.centerTuneRequested.connect(heard.append)
        point = w.wf.getViewBox().mapViewToScene(QPointF(145.525, 100))
        pixel = w.glw.mapFromScene(point)
        assert w.glw.viewport().rect().contains(pixel)
        QTest.mouseDClick(w.glw.viewport(), Qt.LeftButton, pos=pixel)
        QApplication.processEvents()
        assert heard == [145_525_000]
    finally:
        w.close()
