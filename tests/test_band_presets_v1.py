"""V1 LCD shortcuts and dark checkbox regression tests.

Presets are exact frequencies, unlike the rolling band-stack selector.
All tests run without a physical receiver.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pt2vhf.config import Config
from pt2vhf.memory import BAND_PLAN, band_for
from pt2vhf.ui.main_window import MainWindow, STYLE


@pytest.mark.parametrize("name,mhz,mode", [
    ("2 m", 146.000, "NFM"),
    ("70 cm", 433.000, "NFM"),
    ("915 MHz", 915.000, "NFM"),
    ("Aviação (VHF)", 123.450, "AM"),
    ("FM Broadcast", 100.000, "WFM"),
])
def test_presets_pick_exact_frequency_without_grid_rounding(name, mhz, mode):
    band = next(b for b in BAND_PLAN if b.name == name)

    class Harness:
        def __init__(self):
            self.engine = SimpleNamespace(vfo=14_200_000)
            self.cfg = {"band_stacks": {}}
            self.called = []
        def _band_unsupported(self, _band):
            return ""
        def _remember_current_band(self):
            self.called.append(("remember",))
        def _freq_supported(self, frequency):
            return True
        def set_step(self, step):
            self.called.append(("step", step))
        def set_mode(self, selected):
            self.called.append(("mode", selected))
        def tune(self, frequency, snap):
            self.called.append(("tune", frequency, snap))

    receiver = Harness()
    MainWindow._goto_band(receiver, band)
    assert receiver.called[-2] == ("mode", mode)
    assert receiver.called[-1] == ("tune", mhz * 1_000_000, False)
    assert band.start <= mhz * 1_000_000 <= band.end


def test_existing_band_classification_is_unchanged():
    assert band_for(146e6).name == "2 m"
    assert band_for(433e6).name == "70 cm"
    assert band_for(123.45e6).name == "Aviação (VHF)"
    assert band_for(100e6).name == "FM Broadcast"
    assert band_for(915e6).name == "915 MHz"
    assert len({b.name for b in BAND_PLAN}) == len(BAND_PLAN)


def test_band_button_label_and_mode_typography(qt_lifecycle):
    from pt2vhf.ui.bandkeys import BandKeys
    w = BandKeys(["2 m", "70 cm", "915 MHz", "Aviação (VHF)", "FM Broadcast"])
    try:
        expected = {
            "2 m": "2m", "70 cm": "433 MHz", "915 MHz": "915 MHz",
            "Aviação (VHF)": "AIR", "FM Broadcast": "FM",
        }
        assert {name: btn.text() for name, btn in w.buttons.items()} == expected
        for btn in w.buttons.values():
            assert btn.font().family() == "Consolas"
            assert btn.font().bold()
            assert "font-family: Consolas" in btn.styleSheet()
        assert w.layout().columnCount() == 5
    finally:
        w.close()


def test_new_915_button_added_once_to_old_user_preferences(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"bands_visible":["2 m","Aviação (VHF)"]}', encoding="utf-8")
    cfg = Config(path)
    assert cfg["bands_visible"] == ["2 m", "Aviação (VHF)", "915 MHz"]
    cfg["bands_visible"].remove("915 MHz")
    cfg.save()
    again = Config(path)
    assert again["bands_visible"] == ["2 m", "Aviação (VHF)"]
    assert again["bands_v1_migrated"] is True


def test_checkbox_states_are_explicit_in_dark_theme():
    for state in ("QCheckBox::indicator {", "QCheckBox::indicator:checked {",
                  "QCheckBox::indicator:disabled {"):
        assert state in STYLE
    assert "border: 2px solid #91a6b9" in STYLE
    assert "background: #f0b44a" in STYLE
