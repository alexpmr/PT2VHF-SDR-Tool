"""Histórico/exportação de legendas locais de fonia."""
from __future__ import annotations

import csv
import time

from ..live_caption import model_installed

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog,
                               QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)


class LiveCaptionsPanel(QWidget):
    downloadRequested = Signal(str)
    HEADERS = ("Hora", "MHz", "Modo", "Idioma detectado", "Indicativos", "Texto original")

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        main = QVBoxLayout(self)
        # Separate settings from the caption history: both are hosted under Ferramentas.
        self.settings_widget = QWidget()
        settings_layout = QVBoxLayout(self.settings_widget)
        top = QHBoxLayout()
        top.addWidget(QLabel("Modelo local:"))
        self.model = QComboBox()
        for size, label in (("tiny", "Rápido · tiny"), ("base", "Equilibrado · base"),
                            ("small", "Mais preciso · small")):
            self.model.addItem(label, size)
        index = self.model.findData(cfg.get("live_caption_model", "tiny"))
        self.model.setCurrentIndex(max(index, 0))
        self.model.currentIndexChanged.connect(
            lambda _: cfg.__setitem__("live_caption_model", self.model.currentData()))
        top.addWidget(self.model)
        self.download = QPushButton("Baixar modelo")
        self.download.setToolTip("Download explícito do modelo; depois ele funciona sem Internet.")
        self.download.clicked.connect(lambda: self.downloadRequested.emit(self.model.currentData()))
        top.addWidget(self.download)
        top.addWidget(QLabel("Idioma:"))
        self.language = QComboBox()
        for code, name in (("auto", "Detecção automática"), ("pt", "Português"),
                           ("en", "English"), ("es", "Español"), ("fr", "Français"),
                           ("de", "Deutsch"), ("it", "Italiano"), ("zh", "中文")):
            self.language.addItem(name, code)
        i = self.language.findData(cfg.get("live_caption_language", "auto"))
        self.language.setCurrentIndex(max(i, 0))
        self.language.currentIndexChanged.connect(
            lambda _: cfg.__setitem__("live_caption_language", self.language.currentData()))
        top.addWidget(self.language)
        top.addStretch()
        export = QPushButton("Exportar CSV")
        export.clicked.connect(self.export_csv)
        top.addWidget(export)
        settings_layout.addLayout(top)
        self.model_status = QLabel("")
        settings_layout.addWidget(self.model_status)
        self.model.currentIndexChanged.connect(self.refresh_model_status)
        self.refresh_model_status()
        note = QLabel("Reconhecimento local com faster-whisper: escolha e baixe o modelo uma vez. "
                      "Depois, não precisa de rede durante a transcrição. Áudio nunca é enviado. "
                      "A legenda é gerada em blocos de poucos segundos, não palavra a palavra. "
                      "Tradução automática ainda não está disponível.")
        note.setWordWrap(True)
        settings_layout.addWidget(note)
        settings_layout.addStretch(1)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(5, 460)
        main.addWidget(self.table, 1)

    def refresh_model_status(self, *_):
        size = self.model.currentData()
        ready = model_installed(size)
        self.model_status.setText(
            f"Modelo {size}: instalado — transcrição offline disponível." if ready else
            f"Modelo {size}: não instalado. Clique em Baixar modelo (Internet só neste passo).")
        self.download.setEnabled(not ready)
        return ready

    def set_downloading(self, enabled: bool):
        self.download.setEnabled(not enabled)
        self.model.setEnabled(not enabled)
        if enabled:
            self.model_status.setText("Baixando modelo; o áudio não é enviado à Internet.")

    def add_caption(self, timestamp, text, calls, language, freq, mode):
        row = 0
        self.table.insertRow(row)
        data = [time.strftime("%d/%m %H:%M:%S", time.localtime(timestamp)),
                f"{freq / 1e6:.5f}", mode, language or "auto", ", ".join(calls), text]
        for col, val in enumerate(data):
            self.table.setItem(row, col, QTableWidgetItem(str(val)))
        if self.table.rowCount() > 500:
            self.table.removeRow(self.table.rowCount() - 1)

    def export_csv(self):
        p, _ = QFileDialog.getSaveFileName(self, "Exportar legendas", "legendas_sdr.csv", "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(self.HEADERS)
            for row in range(self.table.rowCount()):
                w.writerow([self.table.item(row, col).text() if self.table.item(row, col) else ""
                            for col in range(self.table.columnCount())])
