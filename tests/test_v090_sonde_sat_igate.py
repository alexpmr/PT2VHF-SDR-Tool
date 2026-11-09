"""Regressões da v0.9.0: FI +12kHz, estrutura de decoder, APRS RX-only, satélites."""
from __future__ import annotations

import datetime as dt
import numpy as np
import pytest

from pt2vhf.aprs_igate import gate_line, ReceiveOnlyIGate, clean_call
from pt2vhf.sonde_rx import ChannelIQ, build_decoder_commands
from pt2vhf.satellites import parse_tles, receive_doppler_hz, look_angle, next_passes


def test_sonde_iq_uses_current_sdr_center_and_offsets_to_baseband_zero():
    """Uma RS41 em VFO-150k deve aparecer centrada em 0 Hz no IQ de 48k."""
    fs = 1_200_000
    f0 = 402_500_000
    center = f0 + 150_000
    n = np.arange(120_000, dtype=np.float32)
    iq = (0.7 * np.exp(2j * np.pi * (-150_000 / fs) * n)).astype(np.complex64)
    ch = ChannelIQ(fs, f0)
    raw = ch.convert(iq, center)
    assert len(raw) > 4000
    v = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, 2)
    z = v[:, 0] + 1j * v[:, 1]
    mean_phase = np.angle(np.mean(z[120:] * z[119:-1].conjugate()))
    measured_hz = mean_phase * 48000 / (2 * np.pi)
    assert abs(measured_hz) < 500


def test_sonde_channel_rejects_out_of_band():
    ch = ChannelIQ(1_200_000, 402_500_000)
    with pytest.raises(ValueError):
        ch.convert(np.ones(4096, np.complex64), 140_000_000)
    with pytest.raises(ValueError):
        build_decoder_commands(399_999_000, "fsk_demod", "rs41mod")
    a, b = build_decoder_commands(402_500_000, "fsk_demod", "rs41mod")
    assert "--cs16" in a
    assert a[a.index("-b") + 1] == "-5000"
    assert a[a.index("-u") + 1] == "5000"
    assert "--softin" in b
    assert "--stats=5" in a
    assert "--jsnsubfrm1" in b
    assert b[-1] == "402500000"


def test_aprs_rf_rx_only_rejects_internet_retransmit_and_blocked_path():
    assert clean_call("pt2vhf-10") == "PT2VHF-10"
    assert gate_line("PY2SIM-9>APRS,WIDE1-1:!1234.00S/04800.00W-test", "PT2VHF") == (
        "PY2SIM-9>APRS,WIDE1-1,qAO,PT2VHF:!1234.00S/04800.00W-test")
    assert gate_line("PY2SIM>APRS,TCPIP*:!1234", "PT2VHF") is None
    assert gate_line("PY2SIM>APRS,RFONLY:!1234", "PT2VHF") is None
    assert gate_line("PY2SIM>APRS,WIDE1-1:}THIRDPARTY", "PT2VHF") is None
    assert gate_line("PY2SIM>APRS:hello\nother", "PT2VHF") is None
    with pytest.raises(ValueError):
        ReceiveOnlyIGate("PT2VHF", "not-verified-passcode")
    worker = ReceiveOnlyIGate("PT2VHF", "12345")
    assert worker.submit("PY2SIM>APRS:!packet")
    assert not worker.submit("PY2SIM>APRS:!packet")
    assert worker.dropped == 1
    assert worker.sent == 0  # não dispara conexão nem TX RF sem start()


ISS_TLE = """ISS (ZARYA)
1 25544U 98067A   24278.39451442  .00011847  00000-0  20648-3 0  9994
2 25544  51.6420 143.3000 0006993 222.0601 245.1151 15.48846096473965
"""


def test_satellite_tle_and_receive_doppler():
    sats = parse_tles(ISS_TLE)
    assert len(sats) == 1
    assert sats[0].name == "ISS (ZARYA)"
    # Afastamento: RX deve sintonizar abaixo da nominal.
    assert receive_doppler_hz(145_800_000, 7.0) < 0
    assert receive_doppler_hz(145_800_000, -7.0) > 0
    at = dt.datetime(2024, 10, 4, 10, 0, tzinfo=dt.timezone.utc)
    p = look_angle(sats[0], -15.8, -47.9, at)
    assert 0 <= p.az_deg <= 360
    assert -90 <= p.el_deg <= 90
    assert p.range_km > 300
    passes = next_passes(sats[0], -15.8, -47.9, at, hours=1)
    assert isinstance(passes, list)


def test_mainwindow_contains_new_decoder_and_orbital_panels(qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow
    w = MainWindow()
    try:
        assert w.decoder_tabs.widget(3).widget() is w.dec_panel
        assert w.scan_panel.tabs.indexOf(w.dec_panel) == -1
        assert w.sonde_area.indexOf(w.sonde_panel) >= 0
        assert w.sonde_area.indexOf(w.sonde_feed) >= 0
        assert w.tabs.indexOf(w.pages["decode"]) >= 0
        assert w.decoder_tabs.tabText(0) == "ADS-B"
        assert w.decoder_tabs.tabText(2) == "AIS"
        assert "Satélites" not in [w.tabs.tabText(i) for i in range(w.tabs.count())]
        assert not hasattr(w, "igate_panel")
        assert hasattr(w, "sat_panel")  # módulo preservado; aba removida
        assert w.engine.iq_listeners == []
        assert w.sonde_panel.start.isEnabled()
    finally:
        w.close()


def test_sonde_iq_streaming_has_no_boundary_phase_discontinuity():
    """O streaming deve produzir o mesmo IQ de um processamento monobloco."""
    fs = 1_200_000
    station, center = 402_500_000, 402_650_000
    n = np.arange(163_843, dtype=np.float64)
    signal = (0.65 * np.exp(-2j * np.pi * 150_000 / fs * n)).astype(np.complex64)
    contiguous = ChannelIQ(fs, station).convert(signal, center)
    decoder = ChannelIQ(fs, station)
    pieces = []
    start = 0
    while start < len(signal):
        end = min(len(signal), start + 8191)
        pieces.append(decoder.convert(signal[start:end], center))
        start = end
    streamed = b"".join(pieces)
    assert len(streamed) == len(contiguous)
    mono = np.frombuffer(contiguous, dtype="<i2").astype(np.int32)
    split = np.frombuffer(streamed, dtype="<i2").astype(np.int32)
    assert np.percentile(np.abs(mono - split), 99) <= 2
