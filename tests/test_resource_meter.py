"""Medidor CPU/RAM no cabeçalho: cálculo, layout e atualização sem hardware."""
from __future__ import annotations

from pt2vhf.resource_monitor import ProcessResourceSampler, process_rss_bytes


def test_cpu_usage_percent_is_normalized_to_logical_cores():
    elapsed = iter((100.0, 102.0))
    cpu_elapsed = iter((5.0, 5.8))
    sampler = ProcessResourceSampler(clock=lambda: next(elapsed),
                                     cpu_clock=lambda: next(cpu_elapsed),
                                     cpu_count=8,
                                     rss_reader=lambda: 867 * 1024 * 1024)
    cpu, rss = sampler.sample()
    assert cpu is not None and abs(cpu - 5.0) < 1e-8
    assert rss == 867 * 1024 * 1024


def test_nonpositive_interval_and_unavailable_rss_do_not_invent_data():
    sampler = ProcessResourceSampler(
        clock=lambda: 10.0,
        cpu_clock=lambda: 20.0,
        cpu_count=4,
        rss_reader=lambda: None,
    )
    assert sampler.sample() == (None, None)


def test_meter_displays_live_process_usage(qt_lifecycle):
    from pt2vhf.ui.resource_meter import ResourceMeter

    class Stub:
        def sample(self):
            return 7.1, 867 * 1024 * 1024

    meter = ResourceMeter(sampler=Stub())
    try:
        assert meter.objectName() == "resourceMeter"
        assert meter.width() <= 120 and meter.height() <= 50
        assert meter._timer.interval() == 2000
        assert meter.cpu_value.text() == "—"
        meter.refresh()
        assert meter.cpu_value.text() == "7.1%"
        assert meter.ram_value.text() == "867 MB"
        assert "PT2VHF SDR Tool" in meter.toolTip()
    finally:
        meter.close()


def test_meter_handles_missing_data_without_crashing(qt_lifecycle):
    from pt2vhf.ui.resource_meter import ResourceMeter

    class Stub:
        def sample(self):
            return None, None

    meter = ResourceMeter(sampler=Stub())
    try:
        meter.refresh()
        assert meter.cpu_value.text() == "—"
        assert meter.ram_value.text() == "—"
    finally:
        meter.close()


def test_meter_is_in_top_header_not_in_status_bar(monkeypatch, tmp_path, qt_lifecycle):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from pt2vhf.ui.main_window import MainWindow

    w = MainWindow()
    try:
        assert w.resource_meter.parentWidget() is w.header
        assert w.resource_meter.objectName() == "resourceMeter"
        assert w.utc_label.parentWidget() is w.header
        assert w.header.layout().indexOf(w.resource_meter) < w.header.layout().indexOf(w.utc_label)
    finally:
        w.close()
