"""0.5.0: abas superiores, versão no topo, modo apresentação, reconectar ao abrir, web sem chave."""
import json
import os
import socket
import struct
import threading
import urllib.request

import numpy as np
import pytest

from pt2vhf.webserver import WebServer, detect_lan_ipv4, is_private_lan

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


def test_private_lan_addresses():
    for ip in ("10.1.2.3", "172.16.0.9", "172.31.255.1", "192.168.0.10", "169.254.3.4", "fe80::1", "fd00::5",
               "::ffff:192.168.1.7"):
        assert is_private_lan(ip), ip
    for ip in ("8.8.8.8", "172.32.0.1", "100.64.0.1", "2001:db8::1", "11.0.0.1"):
        assert not is_private_lan(ip), ip


def test_web_lan_without_key():
    ip = detect_lan_ipv4()
    if ip.startswith("127.") or not is_private_lan(ip):
        pytest.skip("sem interface de rede privada")
    w = WebServer(lambda: {"mode": "NFM"}, lambda: None, lan=True, port=0, require_key=False)
    w.start()
    w.port = w._httpd.server_address[1]
    try:
        assert "key=" not in w.url(True)
        with urllib.request.urlopen(f"http://{ip}:{w.port}/state", timeout=5) as r:
            assert r.status == 200 and json.loads(r.read())["mode"] == "NFM"
    finally:
        w.stop()


def _window(tmp_path, monkeypatch, cfg=None):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    if cfg:
        d = tmp_path / "PT2VHF-SDR-Tool"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    from pt2vhf.ui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = MainWindow()
    w.show()
    app.processEvents()
    return app, w


def test_top_tabs_header_and_levels(tmp_path, monkeypatch):
    app, w = _window(tmp_path, monkeypatch)
    titles = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert titles == ["Receptor", "Memórias / Varredura", "Scanner", "ADS-B", "AIS",
                      "Sondas Meteorológicas", "Receptores extras", "Satélites", "Configurações"]
    sub = [w.settings_tabs.tabText(i) for i in range(w.settings_tabs.count())]
    assert sub[:2] == ["Receptor", "Modo / Filtro"]
    assert w.mode_panel.mode_btns == {}  # modos só no display
    assert w.version_btn.parent() is w.header  # indicador de versão no topo
    assert w.version_btn.text() == "Verificar atualizações"
    w.rx_panel.source.setCurrentText("Simulador")  # simulador explícito: primeira execução prefere RTL-SDR
    w.power_btn.click()  # liga pelo cabeçalho
    assert w.engine.running and w.rx_panel.start_btn.isChecked() and w.power_btn.text().startswith("■")
    w.apply_level("Essencial")
    assert not w.tabs.isTabVisible(w.tabs.indexOf(w.pages["scan"]))
    assert not w.tabs.isTabVisible(w.tabs.indexOf(w.pages["extras"]))
    w.apply_level("Avançado")
    assert all(w.tabs.isTabVisible(i) for i in range(w.tabs.count()))
    w.power_btn.click()
    assert not w.engine.running and w.power_btn.text().startswith("▶")
    w.close()


def test_presentation_mode(tmp_path, monkeypatch):
    app, w = _window(tmp_path, monkeypatch)
    w.set_presentation(True)
    app.processEvents()
    assert w.isFullScreen() and w.cfg["presentation"]
    assert not w.menuBar().isVisible() and not w.header.isVisible() and not w.tabs.tabBar().isVisible()
    assert w.wf.isVisible() and w.lcd.isVisible()
    w._escape()
    app.processEvents()
    assert not w.isFullScreen() and w.menuBar().isVisible() and w.header.isVisible()
    w.set_presentation(True)
    w.close()  # lembra que estava em apresentação
    saved = json.loads((tmp_path / "PT2VHF-SDR-Tool" / "config.json").read_text(encoding="utf-8"))
    assert saved["presentation"] is True


def _fake_rtl_tcp():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve():
        try:
            c, _ = srv.accept()
        except OSError:
            return
        c.sendall(b"RTL0" + struct.pack(">II", 5, 29))
        c.settimeout(0.2)
        data = np.full(240_000, 127, np.uint8).tobytes()
        try:
            for _ in range(40):
                try:
                    c.sendall(data)
                    c.recv(64)
                except socket.timeout:
                    pass
        except OSError:
            pass
        c.close()
    threading.Thread(target=serve, daemon=True).start()
    return srv, srv.getsockname()[1]


def test_reconnects_receiver_on_start(tmp_path, monkeypatch):
    srv, port = _fake_rtl_tcp()
    app, w = _window(tmp_path, monkeypatch, {"source": "rtl_tcp", "rtl_tcp_host": "127.0.0.1",
                                             "rtl_tcp_port": port, "sample_rate": 240_000, "rx_was_on": True})
    try:
        w._auto_reconnect()
        assert w.engine.running and w.power_btn.isChecked()
        w.close()
        saved = json.loads((tmp_path / "PT2VHF-SDR-Tool" / "config.json").read_text(encoding="utf-8"))
        assert saved["rx_was_on"] is True and saved["source"] == "rtl_tcp"
    finally:
        srv.close()


def test_reconnect_missing_device_warns_without_dialog(tmp_path, monkeypatch):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # nada escutando
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: pytest.fail("diálogo modal na reconexão"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("diálogo modal na reconexão"))
    app, w = _window(tmp_path, monkeypatch, {"source": "rtl_tcp", "rtl_tcp_host": "127.0.0.1",
                                             "rtl_tcp_port": port, "rx_was_on": True})
    w._auto_reconnect()
    assert not w.engine.running
    assert "Reconexão automática" in w.rx_panel.info.text()
    w.close()
    saved = json.loads((tmp_path / "PT2VHF-SDR-Tool" / "config.json").read_text(encoding="utf-8"))
    assert saved["rx_was_on"] is False


def test_simulator_is_not_reconnected(tmp_path, monkeypatch):
    app, w = _window(tmp_path, monkeypatch)
    w.rx_panel.source.setCurrentText("Simulador")
    w.power_btn.click()
    assert w.engine.running
    w.close()
    saved = json.loads((tmp_path / "PT2VHF-SDR-Tool" / "config.json").read_text(encoding="utf-8"))
    assert saved["rx_was_on"] is False
