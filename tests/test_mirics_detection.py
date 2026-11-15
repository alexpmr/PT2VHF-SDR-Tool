"""RSP discovery supports SDRplay API or Mirics without confusing RTL-SDR."""
from pt2vhf.sources.mirics import (
    SOURCE_NAME, MISSING_DRIVER, enumerate_mirics, enumerate_rsp_devices,
    device_backend, is_mirics_device, is_sdrplay_device, is_rsp_device,
)


def test_mirics_recognizes_known_soapy_drivers():
    assert is_mirics_device({"driver": "miri", "label": "Mirics MSi2500"})
    assert is_mirics_device({"driver": "soapyMiri", "serial": "x"})
    assert is_mirics_device({"driver": "mirisdr"})


def test_sdrplay_api_is_separate_backend():
    assert is_sdrplay_device({"driver": "sdrplay", "label": "RSP1"})
    assert is_sdrplay_device({"driver": "SDRPLAY3", "label": "RSP1"})
    assert device_backend({"driver": "sdrplay"}) == "SDRplay API"
    assert device_backend({"driver": "mirisdr"}) == "Mirics"
    assert not is_mirics_device({"driver": "sdrplay", "label": "RSP1"})
    assert not is_sdrplay_device({"driver": "miri", "label": "RSP1"})


def test_rsp_excludes_rtlsdr_and_product_names_without_driver():
    assert not is_rsp_device({"driver": "rtlsdr"})
    assert not is_rsp_device({"label": "MSi2500 but driver unknown"})
    assert not is_rsp_device({"driver": "hackrf", "label": "SDRplay RSP1"})
    assert not is_rsp_device({"driver": "unregistered"})


def test_mirics_enumerates_only_supported_drivers():
    items = enumerate_mirics(lambda: [
        {"driver": "rtlsdr", "label": "RTL"},
        {"driver": "miri", "label": "Mirics MSi2500"},
        {"driver": "soapyMiri", "serial": "test"},
        {"driver": "sdrplay", "label": "RSP1"},
    ])
    assert len(items) == 2
    assert items[0].startswith("driver=miri,")
    assert items[1].startswith("driver=soapyMiri,")


def test_dual_backend_discovery_shows_choice_without_overwriting_usb_driver():
    options = enumerate_rsp_devices(lambda: [
        {"driver": "sdrplay", "label": "RSP1 API", "serial": "ABC"},
        {"driver": "miri", "label": "MSi2500 alternate", "serial": "XYZ"},
        {"driver": "rtlsdr", "label": "R820T"},
    ])
    assert len(options) == 2
    assert options[0][0].startswith("SDRplay API")
    assert options[0][1].startswith("driver=sdrplay")
    assert options[1][0].startswith("Mirics")
    assert options[1][1].startswith("driver=miri")


def test_rsp_missing_optional_drivers_is_graceful():
    assert enumerate_rsp_devices(lambda: []) == []
    assert enumerate_rsp_devices(lambda: (_ for _ in ()).throw(RuntimeError("missing"))) == []
    assert "SoapySDRUtil --find" in MISSING_DRIVER


def test_receiver_has_dedicated_rsp_source():
    from pt2vhf.ui.panels import SOURCES
    assert SOURCE_NAME in SOURCES


def test_receiver_selector_keeps_driver_descriptors_separate(monkeypatch, qt_lifecycle):
    from pt2vhf.config import Config
    import pt2vhf.ui.panels as p
    monkeypatch.setattr(p, "enumerate_rsp_devices", lambda: [
        ("SDRplay API — RSP1", "driver=sdrplay,serial=one"),
        ("Mirics — MSi2500", "driver=miri,serial=two"),
    ])
    panel = p.ReceiverPanel(Config())
    try:
        panel.source.setCurrentText(SOURCE_NAME)
        assert panel.device.count() == 2
        panel.device.setCurrentIndex(1)
        got = []
        panel.startRequested.connect(got.append)
        panel.start_btn.click()
        assert len(got) == 1
        assert got[0]["soapy_args"] == "driver=miri,serial=two"
        assert got[0]["source"] == SOURCE_NAME
    finally:
        panel.close()
