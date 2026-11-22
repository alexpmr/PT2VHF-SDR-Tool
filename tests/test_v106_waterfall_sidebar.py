"""v1.0.6: real waterfall resolution, honest IQ zoom and sidebar regression."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication
from pt2vhf.ui.waterfall import SpectrumWaterfall


def _waterfall(qt_lifecycle):
    w = SpectrumWaterfall()
    w.resize(1170, 780)
    w.show()
    QApplication.processEvents()
    return w


def test_native_fft_detail_is_preserved_at_100khz_zoom(qt_lifecycle):
    """Two 880 Hz-separated carriers cannot collapse into the old 1.4 kHz pixels."""
    w = _waterfall(qt_lifecycle)
    n = 32768
    fs = 2_880_000
    center = 432_000_000
    bins = np.full(n, -92.0, dtype=np.float32)
    bins[n // 2] = -26.0
    bins[n // 2 + 10] = -34.0
    try:
        w.add_line(bins, center, fs)
        w.spec.setXRange(431.95, 432.05, padding=0)
        QApplication.processEvents()
        w._redraw_history()
        choice = w._view_selection()
        assert choice is not None
        assert choice[3] >= 1000, "100 kHz crop should use ~1138 native FFT bins"
        w.add_line(bins, center, fs)
        row = w._buf[0]
        peaks = np.flatnonzero(row > -45.0)
        assert len(peaks) == 2
        assert peaks[1] - peaks[0] >= 8
        assert w._source_fft_size == n
    finally:
        w.close()


def test_zoom_out_is_clamped_to_actual_iq_band(qt_lifecycle):
    w = _waterfall(qt_lifecycle)
    try:
        w.add_line(np.full(4096, -80, dtype=np.float32), 145_500_000, 200_000)
        w.spec.setXRange(145.0, 146.0, padding=0)
        w._limit_manual_zoom()
        lo, hi = w.spec.getViewBox().viewRange()[0]
        assert abs((hi - lo) - 0.2) < 1e-5
        assert abs((lo + hi) / 2 - 145.5) < 1e-5
        w.zoom_to_vfo(500_000)  # 500 kHz preset when receiver only samples 200 kHz
        lo, hi = w.spec.getViewBox().viewRange()[0]
        assert abs((hi - lo) - 0.2) < 1e-5
    finally:
        w.close()


def test_zoom_rebuilds_native_history_and_keeps_frequency_coordinates(qt_lifecycle):
    w = _waterfall(qt_lifecycle)
    try:
        data = np.full(32768, -100.0, dtype=np.float32)
        data[32768 // 2 + 5] = -22.0
        w.add_line(data, 432_000_000, 2_880_000)
        w.spec.setXRange(431.96, 432.04, padding=0)
        w._redraw_history()
        first = w._buf[0].copy()
        assert first.max() > -40.0
        assert (w._image_right_mhz - w._image_left_mhz) < 0.083
        w.reset_zoom()
        w._redraw_history()
        assert w._buf is not None
        assert w._raw_lines and len(w._raw_lines[0][0]) == 32768
        assert w._raw_lines[0][0].dtype == np.float16
        assert w._buf.shape[1] <= w.MAX_WF_COLS
        w.spec.setXRange(431.96, 432.04, padding=0)
        w._redraw_history()
        assert abs(w._buf[0].max() - first.max()) < 0.5
    finally:
        w.close()


def test_full_band_downsampling_uses_mean_power_not_maximum(qt_lifecycle):
    w = _waterfall(qt_lifecycle)
    try:
        data = np.full(32768, -100.0, dtype=np.float32)
        data[32768 // 2] = -20.0
        w.add_line(data, 432_000_000, 2_880_000)
        w.reset_zoom()
        w._redraw_history()
        # A max-pooling implementation returns -20 dBFS; a wide pixel
        # combining many FFT bins must report its average received power.
        assert w._buf.shape[1] < 32768
        assert -60 < float(np.max(w._buf[0])) < -21
    finally:
        w.close()


def test_sidebar_toggle_persists_and_expands_receiver(tmp_path, monkeypatch, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()
    w.resize(1380, 820)
    w.show()
    QApplication.processEvents()
    try:
        assert w.audio_action.isChecked()
        assert w.audio_scroll.isVisible()
        w.sidebar_btn.click()
        QApplication.processEvents()
        assert not w.audio_action.isChecked()
        assert not w.audio_scroll.isVisible()
        assert "Mostrar" in w.sidebar_btn.text()
        assert w.wf.isVisible()
    finally:
        w.close()
    q = MainWindow()
    q.show()
    QApplication.processEvents()
    try:
        assert not q.audio_action.isChecked()
        assert "Mostrar" in q.sidebar_btn.text()
        q.sidebar_btn.click()
        QApplication.processEvents()
        assert q.audio_action.isChecked()
        assert q.audio_scroll.isVisible()
    finally:
        q.close()
