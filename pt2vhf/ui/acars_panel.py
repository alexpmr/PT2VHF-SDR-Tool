"""Aba ACARS: decodificador nativo das três frequências VHF AM brasileiras."""
from __future__ import annotations

import csv
import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QGroupBox, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..decoders.acars import ACARS_FREQS_HZ


class AcarsPanel(QWidget):
    startRequested = Signal()
    stopRequested = Signal()
    COLUMNS = ("Hora", "MHz", "Matrícula", "Voo", "Label", "Bloco", "Nº msg", "Texto")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages: list[dict] = []
        lay = QVBoxLayout(self)
        box = QGroupBox("Recepção RF pelo SDR atual (um modo por vez)")
        bl = QVBoxLayout(box)
        row = QHBoxLayout()
        freqs = " / ".join(f"{f / 1e6:.3f}" for f in ACARS_FREQS_HZ)
        self.start = QPushButton(f"Receber ACARS ({freqs} MHz)")
        self.stop = QPushButton("Parar")
        self.stop.setEnabled(False)
        self.start.clicked.connect(self.startRequested.emit)
        self.stop.clicked.connect(self.stopRequested.emit)
        export = QPushButton("Exportar CSV")
        export.clicked.connect(self._export)
        clear = QPushButton("Limpar")
        clear.clicked.connect(self.clear)
        for w in (self.start, self.stop, export, clear):
            row.addWidget(w)
        row.addStretch(1)
        bl.addLayout(row)
        self.status = QLabel(
            "Decodificador nativo do PT2VHF (MSK 2400 bit/s, CRC verificado). O SDR é "
            "sintonizado em 131,550 MHz AM e as três frequências são decodificadas juntas.")
        self.status.setWordWrap(True)
        self.status.setObjectName("hintLabel")
        bl.addWidget(self.status)
        lay.addWidget(box)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)

    def running(self, on: bool):
        self.start.setEnabled(not on)
        self.stop.setEnabled(on)

    def add_message(self, msg: dict):
        self.messages.insert(0, msg)
        del self.messages[1000:]
        values = (time.strftime("%d/%m %H:%M:%S", time.localtime(msg.get("timestamp", time.time()))),
                  f"{msg.get('freq_mhz', 0):.3f}", msg.get("reg", ""), msg.get("flight", ""),
                  msg.get("label", ""), msg.get("block_id", ""), msg.get("msg_no", ""),
                  msg.get("text", "").replace("\r", " ").replace("\n", " "))
        self.table.insertRow(0)
        for col, value in enumerate(values):
            self.table.setItem(0, col, QTableWidgetItem(str(value)))
        while self.table.rowCount() > 1000:
            self.table.removeRow(self.table.rowCount() - 1)
        self.status.setText(f"{len(self.messages)} mensagens ACARS com CRC válido")

    def clear(self):
        self.messages.clear()
        self.table.setRowCount(0)

    def _export(self):
        if not self.messages:
            QMessageBox.information(self, "ACARS", "Nenhuma mensagem para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", "acars.csv", "CSV (*.csv)")
        if not path:
            return
        keys = ("timestamp", "freq_mhz", "mode", "reg", "flight", "label", "block_id",
                "msg_no", "ack", "text")
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.messages)
        except OSError as exc:
            QMessageBox.warning(self, "ACARS", str(exc))
