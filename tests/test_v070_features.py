"""Regressões dos recursos incrementais pós-0.6: medidores, ocupação e legendas."""
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from pt2vhf.occupancy import OccupancyHistory


def test_occupancy_minutes_and_persistence(tmp_path):
    path = tmp_path / "occupation.json"
    now = time.time()
    h = OccupancyHistory(path)
    assert h.record(145.570e6, now)
    assert not h.record(145.570e6 + 1000, now + 4)
    assert h.record(145.570e6, now + 61)
    hours, rows = h.matrix(now + 61)
    assert len(hours) == 24
    assert len(rows) == 1
    assert sum(rows[0][1]) == 2
    h.flush(force=True)
    reloaded = OccupancyHistory(path)
    assert sum(reloaded.matrix(now + 61)[1][0][1]) == 2
    reloaded.clear()
    assert reloaded.matrix()[1] == []


def test_occupancy_ignores_invalid_frequency():
    h = OccupancyHistory()
    with pytest.raises(ValueError):
        h.record(-1)


def test_analog_meters_and_style(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt = pytest.importorskip("PySide6.QtWidgets")
    from pt2vhf.ui.analog import AnalogPanel
    app = qt.QApplication.instance() or qt.QApplication([])
    p = AnalogPanel("Valvulado")
    p.set_readings(-91, 0.25)
    assert -147 < p.s_meter.display_value < -33
    assert -60 < p.vu_meter.display_value <= 0
    p.set_style("Militar")
    assert p.s_meter.style == "Militar"
    p.set_style("Estúdio")
    assert p.vu_meter.style == "Estúdio"
    p.close()


def test_live_caption_worker_with_fake_model():
    from pt2vhf.live_caption import LiveCaptionWorker

    class FakeModel:
        def transcribe(self, pcm, **kwargs):
            assert pcm.ndim == 1 and pcm.size > 10_000
            return iter([SimpleNamespace(text="PT2VHF teste")]), SimpleNamespace(language="pt")

    done = threading.Event()
    received = []
    def callback(ts, text, calls, lang, meta):
        received.append((text, calls, lang, meta))
        done.set()
    worker = LiveCaptionWorker(callback, sample_rate=48000, seconds=2,
                               model=FakeModel(), meta_provider=lambda: (145.57e6, "NFM"))
    worker.feed(np.full(96_000, 0.1, dtype=np.float32))
    assert done.wait(10), "worker não retornou legenda"
    worker.stop()
    assert received[0][0] == "PT2VHF teste"
    assert received[0][2] == "pt"
    assert received[0][3] == (145.57e6, "NFM")


def test_weak_signal_dsp_preset(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt = pytest.importorskip("PySide6.QtWidgets")
    from pt2vhf.ui.main_window import MainWindow
    app = qt.QApplication.instance() or qt.QApplication([])
    w = MainWindow()
    previous = (w.audio_panel.nb.isChecked(), w.audio_panel.nr.isChecked(),
                w.audio_panel.nr_str.value(), w.audio_panel.agc.isChecked())
    w.weak_btn.setChecked(True)
    assert w.audio_panel.nb.isChecked() and w.audio_panel.nr.isChecked()
    assert w.audio_panel.nr_str.value() >= 24
    w.weak_btn.setChecked(False)
    assert (w.audio_panel.nb.isChecked(), w.audio_panel.nr.isChecked(),
            w.audio_panel.nr_str.value(), w.audio_panel.agc.isChecked()) == previous
    w.close()
