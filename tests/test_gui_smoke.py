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
