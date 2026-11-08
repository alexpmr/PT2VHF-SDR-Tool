"""Histórico/exportação de legendas locais de fonia."""
from __future__ import annotations

import csv
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog,
                               QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)


class LiveCaptionsPanel(QWidget):
    HEADERS = ("Hora", "MHz", "Modo", "Idioma detectado", "Indicativos", "Texto original")

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        main = QVBoxLayout(self)
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
        main.addLayout(top)
        note = QLabel("Requer faster-whisper e modelo disponível localmente. Áudio não sai do computador. "
                      "A legenda é gerada em blocos de poucos segundos, não palavra a palavra. "
                      "Tradução automática ainda não está disponível.")
        note.setWordWrap(True)
        main.addWidget(note)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(5, 460)
        main.addWidget(self.table, 1)

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
