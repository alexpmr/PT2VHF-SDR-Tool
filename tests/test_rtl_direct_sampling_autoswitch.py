"""Regression: R820T must not be trapped at 0.5–28.8 MHz after HF mode.

The same dongle can receive via *different paths*: I/Q direct HF and tuner
VHF/UHF. Tests never require a physical SDR; live RF QA remains necessary.
"""
from __future__ import annotations

from types import SimpleNamespace

from pt2vhf.sources.rtlsdr_source import (
    select_direct_sampling_mode, tuning_range,
)


def test_range_policy_keeps_433_mhz_in_quadrature():
    assert tuning_range("R820T", False, 2)[1] == 28_800_000
    assert tuning_range("R820T", False, 0)[1] >= 1_700_000_000
    assert select_direct_sampling_mode(155_930_000, 1_200_000, 2, 2) == 0
    assert select_direct_sampling_mode(433_920_000, 1_200_000, 2, 2) == 0
    assert select_direct_sampling_mode(14_200_000, 1_200_000, 0, 2) == 2
    assert select_direct_sampling_mode(14_200_000, 1_200_000, 0, 0) == 0
    assert select_direct_sampling_mode(28_780_000, 1_200_000, 2, 2) == 0


def test_ui_retune_vhf_restores_tuner_and_remembers_hf(monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()

    class FakeSource:
        name = "RTL-SDR"
        sample_rate = 1_200_000
        center_freq = 145_570_000
        tuner = "R820T"
        product = "Generic RTL2832U"
        direct_sampling = 2
        modes = []

        def set_direct_sampling(self, mode):
            self.direct_sampling = int(mode)
            self.modes.append(int(mode))

        def check_freq(self, hz):
            low, high = tuning_range(self.tuner, False, self.direct_sampling)
            return "" if low <= hz <= high else "fora do alcance"

    source = FakeSource()
    try:
        w.engine.source = source
        w.engine.vfo = 14_200_000
        w.cfg["direct_sampling"] = 2
        assert w._freq_supported(155_930_000)
        assert source.direct_sampling == 0
        assert source.modes == [0]
        assert w.cfg["direct_sampling"] == 0
        assert w.cfg["hf_direct_sampling_mode"] == 2
        assert w.rx_panel.direct.currentIndex() == 0
        assert w._freq_supported(433_920_000)
        assert source.modes == [0]  # no duplicate driver reconfiguration
        # Switching back into HF restores the explicitly chosen I/Q path.
        assert w._freq_supported(14_200_000)
        assert source.direct_sampling == 2
        assert source.modes == [0, 2]
        assert w.rx_panel.direct.currentIndex() == 2
    finally:
        w.engine.source = None
        w.close()


def test_manual_direct_sampling_in_vhf_is_not_allowed_to_block_tuning(
        monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()

    class FakeSource:
        name = "RTL-SDR"
        sample_rate = 1_200_000
        center_freq = 433_920_000
        direct_sampling = 0
        modes = []
        def set_direct_sampling(self, mode):
            self.modes.append(mode)
            self.direct_sampling = mode
        def check_freq(self, hz):
            return "" if 24e6 <= hz <= 1766e6 else "fora do alcance"

    try:
        w.engine.source = FakeSource()
        w.engine.vfo = 433_920_000
        w._direct_sampling_selected(2)
        assert w.cfg["direct_sampling"] == 0
        assert w.cfg["hf_direct_sampling_mode"] == 2
        assert w.rx_panel.direct.currentIndex() == 0
        assert w.engine.source.modes == []
        assert w._freq_supported(433_920_000)
    finally:
        w.engine.source = None
        w.close()


def test_band_buttons_allow_tuner_even_while_direct_hf_selected(
        monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()

    class FakeSource:
        name = "RTL-SDR"
        tuner = "R820T"
        product = "R820T"
        sample_rate = 1_200_000
        direct_sampling = 2
        def check_freq(self, hz):
            low, high = tuning_range(self.tuner, False, self.direct_sampling)
            return "" if low <= hz <= high else "fora do alcance"

    try:
        w.engine.source = FakeSource()
        w.cfg["direct_sampling"] = 2
        band = SimpleNamespace(start=430_000_000, end=440_000_000, name="70 cm")
        assert w._band_unsupported(band) == ""
    finally:
        w.engine.source = None
        w.close()


def test_saved_hf_path_selects_tuner_on_startup_policy():
    # Before constructing an RTL device, startup resolves the saved mode
    # against the actual VFO/center. This must protect 155.930 and 433 MHz.
    assert select_direct_sampling_mode(433e6, 1_200_000, 2, 2) == 0
    assert select_direct_sampling_mode(155_930_000, 1_200_000, 2, 2) == 0
    assert select_direct_sampling_mode(7_100_000, 1_200_000, 2, 2) == 2


def test_startup_in_433_mhz_ignores_persisted_hf_direct_mode(
        monkeypatch, tmp_path, qt_lifecycle):
    """The saved HF mode must be disabled BEFORE Engine.start opens RF."""
    from pt2vhf.ui.main_window import MainWindow
    from pt2vhf.sources import rtlsdr_source as module

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()
    starts = []

    class FakeRtl:
        name = "RTL-SDR"
        tuner = "R820T"
        library = "standard"
        product = "generic"
        block_size = 16384
        def __init__(self, sample_rate, center_freq, *_args):
            self.sample_rate = sample_rate
            self.center_freq = center_freq
            self.direct_sampling = 0
            self.events = []
        def set_bias_tee(self, on):
            self.events.append(("bias", on))
        def set_direct_sampling(self, mode):
            self.direct_sampling = int(mode)
            self.events.append(("direct", int(mode)))
        def check_freq(self, freq):
            lo, hi = tuning_range(self.tuner, False, self.direct_sampling)
            return "" if lo <= freq <= hi else "fora do alcance"

    def fake_start(src):
        starts.append(src)
        w.engine.source = src

    monkeypatch.setattr(module, "RtlSdrSource", FakeRtl)
    monkeypatch.setattr(w.engine, "start", fake_start)
    monkeypatch.setattr(w, "_apply_receiver_settings", lambda: None)
    monkeypatch.setattr(w, "_update_lcd", lambda: None)

    try:
        w.engine.vfo = 433_920_000
        w.cfg["direct_sampling"] = 2
        w.start_source({
            "source": "RTL-SDR", "sample_rate": 1_200_000,
            "device_index": 0, "gain": None, "ppm": 0
        })
        assert len(starts) == 1
        assert starts[0].direct_sampling == 0
        assert w.cfg["direct_sampling"] == 0
        assert w.cfg["hf_direct_sampling_mode"] == 2
        assert w.rx_panel.direct.currentIndex() == 0
    finally:
        w.engine.source = None
        w.close()
