"""Regressão da 0.6.0: opções iniciais e controles de banda/waterfall."""
import pytest

from pt2vhf.config import Config
from pt2vhf.memory import band_for


def test_first_install_defaults_to_rtl_sdr_advanced(tmp_path):
    cfg = Config(tmp_path / "config.json")
    assert cfg.first_run
    assert cfg["source"] == "RTL-SDR"
    assert cfg["ui_level"] == "Avançado"
    assert cfg["wf_keep_vfo_centered"] is False
    cfg["source"] = "Simulador"
    cfg.save()
    assert Config(cfg.path)["source"] == "Simulador"


def test_60m_in_band_plan():
    b = band_for(5.357e6)
    assert b is not None and b.name == "60 m" and b.mode == "USB"


def test_band_keys_unsupported_tooltip(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt = pytest.importorskip("PySide6.QtWidgets")
    from pt2vhf.ui.bandkeys import BandKeys
    app = qt.QApplication.instance() or qt.QApplication([])
    bar = BandKeys(["40 m", "2 m", "70 cm"])
    bar.refresh(145.570e6, {"40 m": "Fora do alcance"})
    assert bar.buttons["2 m"].isChecked()
    assert not bar.buttons["40 m"].isEnabled()
    assert bar.buttons["40 m"].isHidden()
    assert bar.visible_names == ["2 m", "70 cm"]
    bar.close()


def test_waterfall_center_keeps_zoom(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    qt = pytest.importorskip("PySide6.QtWidgets")
    from pt2vhf.ui.waterfall import SpectrumWaterfall
    app = qt.QApplication.instance() or qt.QApplication([])
    wf = SpectrumWaterfall()
    wf.set_vfo(145.57e6, -6000, 6000)
    wf.spec.setXRange(145.1, 145.3, padding=0)
    old = wf.spec.getViewBox().viewRange()[0]
    wf.center_on_vfo()
    new = wf.spec.getViewBox().viewRange()[0]
    assert abs((old[1] - old[0]) - (new[1] - new[0])) < 0.0001
    assert abs((new[0] + new[1]) / 2 - 145.57) < 0.0001
    wf.close()
