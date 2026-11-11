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


def _click(w, plot, hz, y=100):
    view = plot.getViewBox()
    scene_point = view.mapViewToScene(QPointF(hz / 1e6, y))
    assert view.sceneBoundingRect().contains(scene_point)
    event = SimpleNamespace(button=lambda: Qt.LeftButton, double=lambda: False,
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
