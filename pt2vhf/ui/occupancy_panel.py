"""Mapa de calor das detecções RF nas últimas 24 horas."""
from __future__ import annotations

import csv
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)


class OccupancyPanel(QWidget):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.history = history
        layout = QVBoxLayout(self)
        label = QLabel("Detecções do scanner por frequência (12,5 kHz) e hora nas últimas 24 h. "
                       "Não mede ocupação contínua: cada frequência conta no máximo uma vez por minuto.")
        label.setWordWrap(True)
        layout.addWidget(label)
        buttons = QHBoxLayout()
        refresh = QPushButton("Atualizar mapa")
        refresh.clicked.connect(self.refresh)
        export = QPushButton("Exportar CSV")
        export.clicked.connect(self.export_csv)
        buttons.addWidget(refresh)
        buttons.addWidget(export)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.info = QLabel("")
        layout.addWidget(self.info)
        self.grid = QTableWidget(0, 25)
        self.grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.NoSelection)
        self.grid.verticalHeader().setVisible(False)
        self.grid.horizontalHeader().setStretchLastSection(False)
        self.grid.setColumnWidth(0, 125)
        for c in range(1, 25):
            self.grid.setColumnWidth(c, 48)
        layout.addWidget(self.grid, 1)
        self.refresh()

    def refresh(self):
        hours, rows = self.history.matrix()
        self.grid.setUpdatesEnabled(False)
        try:
            self.grid.setHorizontalHeaderLabels(
                ["MHz"] + [time.strftime("%d/%m %Hh", time.localtime(h)) for h in hours])
            self.grid.setRowCount(len(rows))
            max_count = max((v for _, counts in rows for v in counts), default=0)
            for ri, (freq, counts) in enumerate(rows):
                head = QTableWidgetItem(f"{freq / 1e6:.5f}")
                self.grid.setItem(ri, 0, head)
                for col, value in enumerate(counts, 1):
                    it = QTableWidgetItem(str(value) if value else "")
                    it.setTextAlignment(Qt.AlignCenter)
                    if value and max_count:
                        t = min(1.0, value / max_count)
                        it.setBackground(QColor(28, int(75 + t * 115), int(44 + t * 25)))
                        it.setForeground(QColor("#ffffff"))
                    it.setToolTip(f"{value} detecção(ões) na hora; amostragem por minuto")
                    self.grid.setItem(ri, col, it)
            self.info.setText(f"{len(rows)} frequências · {sum(sum(v) for _, v in rows)} "
                              "detecções amostradas (24 h)")
        finally:
            self.grid.setUpdatesEnabled(True)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar ocupação 24 h", "ocupacao_24h.csv",
                                               "CSV (*.csv)")
        if not path:
            return
        hours, rows = self.history.matrix(limit=100000)
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["frequencia_mhz"] +
                            [time.strftime("%Y-%m-%d %H:00", time.localtime(h)) for h in hours])
            for freq, counts in rows:
                writer.writerow([f"{freq / 1e6:.5f}", *counts])
