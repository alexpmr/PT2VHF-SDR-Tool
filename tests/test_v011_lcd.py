"""Layout LCD vetorial, matriz de cinco colunas e S-meter variável."""
import math

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pt2vhf.ui.lcd import LCDDisplay
from pt2vhf.ui.bandkeys import BandKeys


def test_smeter_no_sample_has_zero_segments_and_levels_increase(qt_lifecycle):
    lcd = LCDDisplay()
    try:
        assert LCDDisplay.meter_segments(-127, False) == 0
        assert LCDDisplay.meter_segments(float("nan")) == 0
        assert LCDDisplay.meter_segments(-150) == 0
        samples = [-147, -141, -129, -117, -105, -93, -73, -53, -33]
        values = [LCDDisplay.meter_segments(x) for x in samples]
        assert values == sorted(values)
        assert len(set(values)) == len(values)
        assert LCDDisplay.meter_segments(-93) == 19
        assert LCDDisplay.meter_segments(-33) == 40
        assert LCDDisplay.meter_segments(-127) == 7
        lcd.set_signal(None, "S0", False)
        assert not lcd.signal_valid
        lcd.set_signal(-107, "S6", True)
        assert lcd.signal_valid
        assert lcd.signal_dbm == -107
        lcd.set_signal(-132, "S2", False)
        assert lcd.signal_dbm == -132
        lcd.set_signal(None, "", False)
        assert LCDDisplay.meter_segments(lcd.signal_dbm, lcd.signal_valid) == 0
    finally:
        lcd.close()


def test_band_matrix_scales_as_single_lcd_and_clicks_work(qt_lifecycle):
    lcd = LCDDisplay()
    keys = BandKeys(parent=lcd)
    lcd.attach_band_keys(keys)
    pressed = []
    lcd.modeClicked.connect(pressed.append)
    try:
        assert keys.layout().columnCount() == 5
        assert len(keys.buttons) >= 15
        for width, height in ((1100, 255), (825, 191), (550, 128), (360, 85)):
            lcd.resize(width, height)
            lcd.show()
            QApplication.processEvents()
            lcd.grab()  # forces the painter to populate interactive regions
            scale, left, top = lcd._canvas()
            rect = lcd.BAND_RECT
            geom = keys.geometry()
            assert abs(geom.x() - (left + scale * rect.x())) < 3
            assert abs(geom.y() - (top + scale * rect.y())) < 3
            assert abs(geom.width() - scale * rect.width()) < 3
            assert geom.right() <= lcd.width()
            assert geom.bottom() <= lcd.height()
            assert len(lcd._key_rects) == 12
            assert len(lcd._digit_rects) == 10
            # Teste de hitbox nos pixels exibidos, não nas coordenadas lógicas.
            mode = next(rect for rect, name in lcd._key_rects if name == "USB")
            x = round(left + mode.center().x() * scale)
            y = round(top + mode.center().y() * scale)
            QTest.mouseClick(lcd, Qt.LeftButton, pos=QPoint(x, y))
            QApplication.processEvents()
            assert pressed[-1] == "USB"
        keys.buttons[next(iter(keys.buttons))].click()
    finally:
        lcd.close()


def test_lcd_theme_band_selection_and_unavailable_bands(qt_lifecycle):
    lcd = LCDDisplay()
    keys = BandKeys(["20 m", "2 m"], lcd)
    lcd.attach_band_keys(keys)
    try:
        for name in ("Âmbar", "Verde", "Azul (negativo)", "Noturno", "Branco"):
            lcd.set_theme(name)
            assert keys._theme == name
        keys.refresh(145_500_000, {"20 m": "O SDR atual não recebe HF"})
        assert keys.buttons["2 m"].isChecked()
        assert not keys.buttons["20 m"].isChecked()
        assert keys.buttons["20 m"].isHidden()
        assert not keys.buttons["20 m"].isEnabled()
        assert not keys.buttons["2 m"].isHidden()
        assert keys.visible_names == ["2 m"]
    finally:
        lcd.close()

def test_manual_scale_keeps_aspect_and_compacts_available_bands(qt_lifecycle):
    lcd = LCDDisplay()
    keys = BandKeys(["20 m", "2 m", "70 cm"], lcd)
    lcd.attach_band_keys(keys)
    try:
        lcd.set_preferred_scale(70)
        assert lcd._preferred_percent == 70
        assert lcd.maximumWidth() == round(lcd.DESIGN_WIDTH * 0.7)
        assert lcd.maximumHeight() == round(lcd.DESIGN_HEIGHT * 0.7)
        assert lcd.sizeHint().width() == round(lcd.DESIGN_WIDTH * 0.7)
        keys.refresh(145_500_000, {"20 m": "Sem recepção HF", "70 cm": "Sem UHF"})
        assert keys.visible_names == ["2 m"]
        assert keys.buttons["20 m"].isHidden()
        assert keys.buttons["70 cm"].isHidden()
        assert keys.buttons["2 m"].isEnabled()
        assert keys.layout().itemAtPosition(0, 0).widget() is keys.buttons["2 m"]
        keys.refresh(433_000_000, {"20 m": "Sem HF"})
        assert keys.visible_names == ["2 m", "70 cm"]
        assert keys.layout().itemAtPosition(0, 1).widget() is keys.buttons["70 cm"]
        lcd.set_preferred_scale(800)
        assert lcd._preferred_percent == 150
        lcd.set_preferred_scale(10)
        assert lcd._preferred_percent == 50
    finally:
        lcd.close()
