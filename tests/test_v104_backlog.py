"""v1.0.4 backlog increments: safe OTA probe, RS41 prerequisites and compact UI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QFormLayout, QMainWindow, QMessageBox,
                               QPushButton, QWidget)

from pt2vhf.config import Config


def test_rs41_prerequisite_check_does_not_execute_binary(tmp_path, monkeypatch, qt_lifecycle):
    from pt2vhf.ui.sonde_decoder_panel import SondeDecoderPanel
    import pt2vhf.ui.sonde_decoder_panel as module

    cfg = Config(tmp_path / "config.json")
    panel = SondeDecoderPanel(cfg)
    monkeypatch.setattr(module.shutil, "which",
                        lambda name: "/tmp/fsk_demod" if name == "fsk_demod" else None)
    try:
        panel.fsk_path.setText("")
        panel.rs_path.setText("")
        found = panel.verify_tools()
        assert found == {"fsk_demod": True, "rs41mod": False}
        assert "AUSENTE" in panel.log.toPlainText()
        assert "RS41 indisponível" in panel.status.text()
        # Absence of executable must remain a prerequisite failure,
        # not a false 'RS41 decoded' status.
        assert panel.table.rowCount() == 0
        assert panel.verify.text() == "Verificar decodificadores"
    finally:
        panel.close()


def test_rs41_copy_diagnostics(qt_lifecycle):
    from PySide6.QtWidgets import QApplication
    from pt2vhf.ui.sonde_decoder_panel import SondeDecoderPanel

    panel = SondeDecoderPanel(Config())
    try:
        panel.log.setPlainText("fsk_demod: ausente")
        panel.copy_diagnostics()
        clipboard = QApplication.clipboard().text()
        assert "diagnóstico RS41" in clipboard
        assert "fsk_demod: ausente" in clipboard
    finally:
        panel.close()


def test_ota_probe_requires_frozen_windows(qt_lifecycle, monkeypatch):
    from pt2vhf.ui.assist_panels import UpdateController
    warnings = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: warnings.append(a[-1]))
    parent = QMainWindow()
    btn = QPushButton(parent)
    ctrl = UpdateController(parent, btn)
    ctrl.kind = "source"
    try:
        ctrl.probe_helper()
        assert warnings and "somente nos executáveis Windows" in warnings[-1]
        assert not ctrl._probe_running
    finally:
        parent.close()


def test_ota_probe_result_includes_log_and_no_install_warning(qt_lifecycle, monkeypatch):
    from pt2vhf.ui.assist_panels import UpdateController

    notices = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *_a: notices.append(_a[-1]))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *_a: notices.append(_a[-1]))
    parent = QMainWindow()
    ctrl = UpdateController(parent, QPushButton(parent))
    try:
        ctrl._probe_running = True
        ctrl._on_probe_finished(True, "READY")
        assert not ctrl._probe_running
        assert "PT2VHF-SDR-Tool-ota-launch.log" in notices[-1]
        assert "não instala versões" in notices[-1]
    finally:
        parent.close()


def test_controls_keep_content_width_and_responsive_forms(qt_lifecycle):
    from pt2vhf.ui.panels import _compact
    from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout,
                                   QLabel, QSlider, QVBoxLayout, QSizePolicy)
    from PySide6.QtCore import Qt

    root = QWidget()
    v = QVBoxLayout(root)
    form = QFormLayout()
    v.addLayout(form)
    cb = QComboBox()
    cb.addItems(["RTL-SDR", "SoapySDR"])
    spin = QDoubleSpinBox()
    slider = QSlider(Qt.Horizontal)
    form.addRow(QLabel("Fonte:"), cb)
    form.addRow(QLabel("Offset:"), spin)
    form.addRow(QLabel("Ganho:"), slider)
    _compact(root)
    try:
        assert form.fieldGrowthPolicy() == QFormLayout.FieldsStayAtSizeHint
        assert form.rowWrapPolicy() == QFormLayout.WrapLongRows
        assert cb.maximumWidth() == 420
        assert spin.maximumWidth() == 180
        assert slider.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    finally:
        root.close()


def test_settings_exposes_native_ota_probe(qt_lifecycle):
    from pt2vhf.ui.settings_panel import SettingsPanel

    cfg = Config()
    panel = SettingsPanel(cfg, ["Essencial", "Intermediário", "Avançado"],
                          ["Âmbar", "Verde"])
    events = []
    panel.testOtaHelper.connect(lambda: events.append("probe"))
    try:
        panel.test_ota_btn.click()
        assert events == ["probe"]
        assert "sem instalar" in panel.test_ota_btn.text()
    finally:
        panel.close()
