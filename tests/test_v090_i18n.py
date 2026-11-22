"""Internacionalização de elementos principais com retorno completo ao português."""
import json


def test_catalog_languages_and_fallback():
    from pt2vhf.i18n import LANGUAGES, translate
    assert [x[0] for x in LANGUAGES] == ["pt", "en", "es", "fr", "de", "it", "zh"]
    assert translate("Receptor", "en") == "Receiver"
    assert translate("Receptor", "es") == "Receptor"
    assert translate("Receptor", "zh") == "接收机"
    assert translate("Receptor", "xx") == "Receptor"
    assert translate("NOT_IN_CATALOG", "fr") == "NOT_IN_CATALOG"


def test_ui_language_changes_without_mutating_internal_values(monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    w = MainWindow()
    try:
        assert w.language_combo.count() == 7
        w.language_combo.setCurrentIndex(w.language_combo.findData("en"))
        assert w.tabs.tabText(0) == "Receiver"
        assert w.tabs.tabText(w.tabs.indexOf(w.pages["decode"])) == "Decoding"
        assert w.tabs.tabText(w.tabs.indexOf(w.pages["tools"])) == "Tools"
        assert w.tools_tabs.tabText(0) == "Transcription"
        assert w.tools_tabs.tabText(1) == "Live captions"
        assert w.cfg["language"] == "en"
        assert w.cfg["mode"] in ("NFM", "AM", "WFM", "USB", "LSB", "CW")
        w.language_combo.setCurrentIndex(w.language_combo.findData("pt"))
        assert w.tabs.tabText(0) == "Receptor"
        assert w.cfg["language"] == "pt"
    finally:
        w.close()
