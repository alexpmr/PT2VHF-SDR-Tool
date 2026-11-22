"""Regressões da organização v0.10.0 e teclas de banda integradas ao LCD."""
from __future__ import annotations

from pt2vhf.traffic import Track


def test_main_navigation_and_lcd_band_theme(monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()
    try:
        pages = [w.tabs.tabText(i) for i in range(w.tabs.count())]
        assert "Decodificadores" not in pages
        assert "APRS iGate RX" not in pages
        assert "Decodificação" in pages and "Ferramentas" in pages
        assert "ADS-B" not in pages and "AIS" not in pages
        assert "Sondas Meteorológicas" not in pages and "Satélites" not in pages
        assert [w.decoder_tabs.tabText(i) for i in range(w.decoder_tabs.count())] == [
            "ADS-B", "Sondas Meteorológicas", "AIS", "APRS / DTMF / CTCSS"]
        assert w.decoder_tabs.widget(3).widget() is w.dec_panel
        assert w.scan_panel.tabs.indexOf(w.dec_panel) == -1
        assert [w.tools_tabs.tabText(i) for i in range(w.tools_tabs.count())] == [
            "Transcrição", "Legendas ao vivo"]
        assert w.sonde_area.indexOf(w.sonde_panel) >= 0
        assert w.sonde_area.indexOf(w.sonde_feed) >= 0
        assert w.band_bar.parentWidget() is w.lcd
        scale, ox, oy = w.lcd._canvas()
        matrix = w.lcd.BAND_RECT
        assert abs(w.band_bar.y() - (oy + matrix.y() * scale)) <= 2
        assert len(w.band_bar.buttons) > 10
        assert w.band_bar.layout().columnCount() == 5
        assert w.band_bar.geometry().right() <= w.lcd.width()
        assert w.band_bar.buttons
        for theme in ("Âmbar", "Verde", "Azul (negativo)", "Noturno", "Branco"):
            w.lcd.set_theme(theme)
            assert w.band_bar._theme == theme
        w._set_visible_bands(["20 m", "2 m"])
        assert w.band_bar.parentWidget() is w.lcd
        assert set(w.band_bar.buttons) == {"20 m", "2 m"}
    finally:
        w.close()



def test_lcd_scale_persists_and_unknown_sdr_hides_unavailable_bands(monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()
    try:
        w._set_lcd_scale(75)
        assert w.lcd._preferred_percent == 75
        assert w.cfg["lcd_scale_percent"] == 75
        # Um SDR V3/R820T sem amostragem direta não recebe 20 metros.
        w.cfg["device_name"] = "0: RTL2832U R820T"
        w.cfg["direct_sampling"] = 0
        w._refresh_band_keys()
        assert w.band_bar.buttons["20 m"].isHidden()
        assert not w.band_bar.buttons["2 m"].isHidden()
        # V4 com upconverter interno recebe HF sem desabilitar a preferência do operador.
        w.cfg["device_name"] = "0: RTL-SDR Blog V4"
        w._refresh_band_keys()
        assert not w.band_bar.buttons["20 m"].isHidden()
        assert "20 m" in w.cfg["bands_visible"]
    finally:
        w.close()
    fresh = MainWindow()
    try:
        assert fresh.cfg["lcd_scale_percent"] == 75
        assert fresh.lcd._preferred_percent == 75
        assert fresh.display_panel.lcd_scale.value() == 75
    finally:
        fresh.close()


def test_sonde_feed_shares_history_and_labeled_map(qt_lifecycle, tmp_path):
    from pt2vhf.ui.traffic_panel import SourceTab
    tab = SourceTab("Sonda", {"traffic_sonda_path": "", "traffic_sonda_auto": False})
    try:
        one = Track("Sonda", "RS41-123", -15.8, -47.9, altitude_m=1000)
        two = Track("Sonda", "RS41-123", -15.79, -47.89, altitude_m=1200)
        tab.add_live_record(one)
        tab.add_live_record(two)
        assert len(tab.history) == 2
        assert len(tab.records) == 1
        assert tab.table.item(0, 0).text() == "RS41-123"
        from pt2vhf.traffic import export_map
        text = export_map(tab.history, tmp_path / "sonda.html").read_text()
        assert "L.polyline" in text and "RS41-123" in text
    finally:
        tab.close()


def test_decoder_iq_diagnostics_and_bounded_capture(tmp_path):
    from pt2vhf.sonde_rx import RS41Receiver
    recv = RS41Receiver(1_200_000, 402_000_000, lambda *_: None)
    d = recv.diagnostics()
    assert d["json_frames"] == 0 and not d["fsk_alive"]
    recv.start_capture(tmp_path / "rs41.c16", duration=1)
    recv._capture_data(b"\x00" * 48000 * 4)
    assert (tmp_path / "rs41.c16").stat().st_size == 48000 * 4
    assert recv.diagnostics()["capture"].endswith("rs41.c16")
    recv.stop()
