"""Regressão: indicadores desmarcados precisam ter contraste no tema escuro."""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


def test_checkbox_style_has_explicit_unchecked_and_disabled_indicators():
    from pt2vhf.ui.main_window import STYLE
    assert "QCheckBox::indicator:unchecked {" in STYLE
    assert "border: 2px solid #9dacbc;" in STYLE
    assert "QCheckBox::indicator:unchecked:hover" in STYLE
    assert "QCheckBox::indicator:unchecked:disabled" in STYLE
    # O estado marcado mantém o desenho/tique nativo do Qt.
    assert "QCheckBox::indicator:checked {" not in STYLE


def test_checkbox_states_render_without_crash():
    from pt2vhf.ui.main_window import STYLE
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QWidget()
    parent.setStyleSheet(STYLE)
    layout = QtWidgets.QVBoxLayout(parent)
    checkboxes = []
    for checked, enabled in ((False, True), (True, True), (False, False)):
        box = QtWidgets.QCheckBox("Teste")
        box.setChecked(checked)
        box.setEnabled(enabled)
        layout.addWidget(box)
        checkboxes.append(box)
    parent.show()
    app.processEvents()
    for checkbox in checkboxes:
        pixmap = checkbox.grab()
        assert not pixmap.isNull()
        assert pixmap.width() > 0 and pixmap.height() > 0
    parent.close()
