"""External upconverter must translate actual tuner controls, not RF presentation."""
import pytest

from pt2vhf.sources.frequency_translation import FrequencyTranslatedSource


class FakeSource:
    name = "RTL-SDR"
    tunable = True
    sample_rate = 1_200_000
    _running = False

    def __init__(self):
        self.center_freq = 107_250_000
        self.commands = []

    def set_center_freq(self, value):
        self.commands.append(value)
        self.center_freq = value
        return True

    def check_freq(self, value):
        return "" if 24e6 <= value <= 1.7e9 else "fora de alcance"


def test_upconverter_100mhz_rf_and_hardware_do_not_mix():
    physical = FakeSource()
    logical = FrequencyTranslatedSource(physical, 100e6)
    assert logical.center_freq == 7_250_000
    assert logical.hardware_center_freq == 107_250_000
    assert logical.check_freq(7_100_000) == ""
    assert logical.set_center_freq(7_100_000)
    assert physical.commands == [107_100_000]
    assert logical.center_freq == 7_100_000


def test_disabled_offset_preserves_ordinary_tuning():
    physical = FakeSource()
    logical = FrequencyTranslatedSource(physical, 0)
    logical.set_center_freq(146_000_000)
    assert physical.center_freq == logical.center_freq == 146_000_000


def test_upconverter_validates_physical_tuning_range():
    logical = FrequencyTranslatedSource(FakeSource(), 100e6)
    assert logical.check_freq(1_650_000_000) == "fora de alcance"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 2e9])
def test_upconverter_rejects_invalid_offsets(bad):
    with pytest.raises(ValueError):
        FrequencyTranslatedSource(FakeSource(), bad)


def test_non_tunable_source_rejected():
    physical = FakeSource()
    physical.tunable = False
    with pytest.raises(ValueError):
        FrequencyTranslatedSource(physical, 100e6)


def test_receiver_panel_passes_converter_options_to_source(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from pt2vhf.config import Config
    from pt2vhf.ui.panels import ReceiverPanel

    app = QApplication.instance() or QApplication([])
    cfg = Config()
    panel = ReceiverPanel(cfg)
    panel.external_converter.setChecked(True)
    panel.converter_offset.setValue(100.0)
    received = []
    panel.startRequested.connect(received.append)
    panel.start_btn.click()
    assert len(received) == 1
    assert received[0]["external_converter_enabled"] is True
    assert received[0]["external_converter_offset_mhz"] == 100.0
    panel.set_running(True)
    assert not panel.converter_offset.isEnabled()
    panel.set_running(False)
    assert panel.converter_offset.isEnabled()
    panel.close()
