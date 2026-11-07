"""Teste de fumaça da interface (executa offscreen)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


def test_main_window_runs_simulator(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtCore import QEventLoop, QTimer
    from pt2vhf.ui.main_window import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    w = MainWindow()
    w.show()
    w.rx_panel.source.setCurrentText("Simulador")
    w.rx_panel.start_btn.setChecked(True)
    assert w.engine.running
    w.set_mode("AM")
    w.tune(145.650e6)
    w.set_mode("NFM")
    w.tune(145.570e6)
    loop = QEventLoop()
    QTimer.singleShot(7500, loop.quit)
    loop.exec()
    assert w.wf._buf is not None
    assert w.dec_panel.counts["aprs"] >= 1
    w.lcd.set_theme("Azul (negativo)")
    w._vfo_action("swap")
    assert w.active_vfo == "B"
    w.close()
    assert not w.engine.running


def test_scanner_and_favorites_gui(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtCore import QEventLoop, QTimer
    from pt2vhf.presets import import_packs
    from pt2vhf.ui.main_window import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    w = MainWindow()
    w.show()
    w.bank.channels = []  # sem as memórias de exemplo (que já cobrem os sinais do simulador)
    import_packs(w.bank, ["marine"], favorite=True)
    w._memories_changed()
    assert len([b for b in w.fav_bar._buttons if isinstance(b, QtWidgets.QToolButton)]) >= 17
    w.rx_panel.start_btn.setChecked(True)
    sp = w.scan_panel
    sp.preset.setCurrentIndex(sp.preset.count() - 1)  # personalizada
    sp.f0.setValue(145.2)
    sp.f1.setValue(145.9)
    sp.only_discover.setChecked(True)
    sp.start.setChecked(True)
    assert w.sscan.running and w.engine.hold_center
    loop = QEventLoop()
    QTimer.singleShot(6000, loop.quit)
    loop.exec()
    assert len(w.sscan.hits) >= 3
    w._update_hits(force=True)
    assert sp.hits.rowCount() == len(w.sscan.hits)
    sp.hits.selectRow(0)
    sp.saveRequested.emit(sp._selected_freqs(), "Descobertas")
    assert any(c.category == "Descobertas" for c in w.bank.channels)
    w.tune(146.0e6)  # sintonia manual interrompe o scanner
    assert not w.sscan.running and not w.engine.hold_center
    w.close()
