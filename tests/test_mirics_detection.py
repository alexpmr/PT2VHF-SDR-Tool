"""Mirics RSP1 clone recognition is opt-in and never claims RTL/SDRplay support."""
from pt2vhf.sources.mirics import (
    SOURCE_NAME, MISSING_DRIVER, enumerate_mirics, is_mirics_device,
)


def test_mirics_recognizes_known_soapy_drivers():
    assert is_mirics_device({"driver": "miri", "label": "Mirics MSi2500"})
    assert is_mirics_device({"driver": "soapyMiri", "serial": "x"})
    assert is_mirics_device({"driver": "mirisdr"})


def test_mirics_excludes_sdrplay_and_rtlsdr():
    assert not is_mirics_device({"driver": "sdrplay", "label": "RSP1"})
    assert not is_mirics_device({"driver": "rtlsdr"})
    assert not is_mirics_device({"label": "MSi2500 but driver unknown"})


def test_mirics_enumerates_only_supported_drivers():
    items = enumerate_mirics(lambda: [
        {"driver": "rtlsdr", "label": "RTL"},
        {"driver": "miri", "label": "Mirics MSi2500"},
        {"driver": "soapyMiri", "serial": "test"},
    ])
    assert len(items) == 2
    assert items[0].startswith("driver=miri,")
    assert items[1].startswith("driver=soapyMiri,")


def test_mirics_no_driver_is_graceful():
    assert enumerate_mirics(lambda: []) == []
    assert enumerate_mirics(lambda: (_ for _ in ()).throw(RuntimeError("missing"))) == []
    assert "SoapySDRUtil --find" in MISSING_DRIVER


def test_receiver_has_dedicated_mirics_source():
    from pt2vhf.ui.panels import SOURCES
    assert SOURCE_NAME in SOURCES
