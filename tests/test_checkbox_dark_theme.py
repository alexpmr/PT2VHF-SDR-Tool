"""Regressão visual: checkboxes desmarcados visíveis no tema escuro."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QCheckBox, QWidget
from pt2vhf.ui.main_window import STYLE


def test_dark_theme_has_explicit_unchecked_and_checked_indicator_styles():
    assert "QCheckBox::indicator:unchecked {" in STYLE
    assert "border: 2px solid #a8bfd1" in STYLE
    assert "QCheckBox::indicator:checked {" in STYLE
    assert "QCheckBox::indicator:unchecked:disabled" in STYLE
    assert "QCheckBox::indicator:checked:disabled" in STYLE
    assert "background: #182631" in STYLE


def test_all_checkbox_states_stay_visible_with_dark_theme(qt_lifecycle):
    parent = QWidget()
    parent.setStyleSheet(STYLE)
    unchecked = QCheckBox("NB", parent)
    checked = QCheckBox("IA neural", parent)
    disabled = QCheckBox("NR", parent)
    checked.setChecked(True)
    disabled.setEnabled(False)
    try:
        parent.resize(270, 120)
        unchecked.move(10, 10)
        checked.move(10, 40)
        disabled.move(10, 70)
        parent.show()
        QApplication.processEvents()
        for box in (unchecked, checked, disabled):
            assert box.isVisible()
            assert box.sizeHint().height() >= 15
            assert box.styleSheet() == ""  # draws from parent theme globally
        assert not unchecked.isChecked()
        assert checked.isChecked()
        assert not disabled.isEnabled()
        unchecked.setChecked(True)
        assert unchecked.isChecked()
        unchecked.setChecked(False)
        assert not unchecked.isChecked()
    finally:
        parent.close()
