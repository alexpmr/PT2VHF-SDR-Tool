"""Legendas: navegação e popup textual sem metadados na área do receptor."""
from __future__ import annotations

import time


def test_caption_pages_and_popup_text_only(monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("PT2VHF_NO_AUTOCONNECT", "1")
    monkeypatch.setenv("PT2VHF_NO_STARTUP_DIALOGS", "1")
    w = MainWindow()
    try:
        assert [w.tools_tabs.tabText(i) for i in range(w.tools_tabs.count())] == [
            "Transcrição", "Legendas ao vivo"]
        assert w.scan_panel.tabs.indexOf(w.live_captions_panel) == -1
        assert w.live_captions_panel.settings_widget.parentWidget() is not None
        assert w.scan_panel.transcribe.parentWidget() is w.live_captions_panel.settings_widget
        assert w.caption_popup.parentWidget() is w.receiver_left

        now = time.time()
        w.cfg["live_caption_enabled"] = True
        w.engine.events.put((
            "live_caption",
            (now, "  Teste de recepção PT2VHF  ", ["PT2VHF"], "pt", (145_500_000, "NFM")),
            now,
        ))
        w._tick()
        assert w.caption_popup.text() == "Teste de recepção PT2VHF"
        assert w.live_captions_panel.table.rowCount() == 1
        assert "MHz" not in w.caption_popup.text()
        assert "NFM" not in w.caption_popup.text()

        w._toggle_live_captions(False)
        assert not w.caption_popup.isVisible()
        assert not w.caption_popup.text()
    finally:
        w.close()


def test_caption_model_missing_opens_tools_not_scanner(monkeypatch, tmp_path, qt_lifecycle):
    from pt2vhf.ui.main_window import MainWindow
    from PySide6.QtWidgets import QMessageBox
    import pt2vhf.transcribe as transcribe

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("PT2VHF_NO_AUTOCONNECT", "1")
    monkeypatch.setenv("PT2VHF_NO_STARTUP_DIALOGS", "1")
    monkeypatch.setattr(transcribe, "backend_available", lambda: False)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    w = MainWindow()
    try:
        w.live_captions_panel.enable_live.setChecked(True)
        assert not w.live_btn.isChecked()
        assert not w.live_captions_panel.enable_live.isChecked()
        assert w.tabs.currentWidget() is w.pages["tools"]
        assert w.tools_tabs.currentWidget() is w.caption_settings_page
    finally:
        w.close()
