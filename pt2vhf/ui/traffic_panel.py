"""Consulta local a feeds externos de ADS-B, AIS e radiossondas.

Não é um demodulador de RF. Requer readsb/dump1090, AIS-catcher/rtl_ais ou
radiosonde_auto_rx configurado para exportar os dados em arquivo local.
"""
from __future__ import annotations

from pathlib import Path
import time

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget, QAbstractItemView)

from ..config import config_dir
from ..traffic import export_csv, export_gpx, export_kml, export_map, load_traffic


class SourceTab(QWidget):
    COLUMNS = ("ID", "Nome / Indicativo", "Lat", "Lon", "Alt. (m)", "Vel. (km/h)",
               "Rumo", "Subida (m/s)", "Dados", "Recebido")

    def __init__(self, kind, cfg, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.cfg = cfg
        self.records = []
        self.history = []
        self.last_stamp = None
        main = QVBoxLayout(self)
        explanation = {
            "ADS-B": "Requer arquivo aircraft.json de readsb/dump1090 (1090 MHz). "
                     "Ex.: C:/readsb/aircraft.json; o SDR não é sintonizado por esta aba.",
            "AIS": "Requer log NMEA !AIVDM do AIS-catcher/rtl_ais (161,975/162,025 MHz). "
                   "A mensagem AIS é decodificada localmente; o sinal RF vem do processo externo.",
            "Sonda": "Importe telemetria JSON de radiosonde_auto_rx ou conversor compatível. "
                     "Para recepção direta do SDR, utilize a aba Recepção RF neste painel.",
        }
        note = QLabel(explanation[kind])
        note.setWordWrap(True)
        note.setObjectName("hintLabel")
        main.addWidget(note)
        row = QHBoxLayout()
        self.file = QLineEdit(cfg.get("traffic_" + kind.lower() + "_path", ""))
        self.file.setPlaceholderText("Caminho do arquivo local gerado pelo decodificador externo…")
        browse = QPushButton("Selecionar…")
        browse.clicked.connect(self._browse)
        row.addWidget(QLabel("Fonte:"))
        row.addWidget(self.file, 1)
        row.addWidget(browse)
        main.addLayout(row)
        bar = QHBoxLayout()
        self.auto = QCheckBox("Atualizar automaticamente a cada 5 s")
        self.auto.setChecked(bool(cfg.get("traffic_" + kind.lower() + "_auto", False)))
        refresh = QPushButton("Atualizar agora")
        refresh.clicked.connect(lambda: self.refresh(force=True))
        export = QPushButton("Exportar CSV")
        export.clicked.connect(self._export)
        bar.addWidget(self.auto)
        bar.addWidget(refresh)
        bar.addWidget(export)
        map_btn = QPushButton("Mapa OSM + rastros")
        map_btn.clicked.connect(self.open_map)
        bar.addWidget(map_btn)
        gpx_btn = QPushButton("GPX / KML")
        gpx_btn.clicked.connect(self._export_tracks)
        bar.addWidget(gpx_btn)
        bar.addStretch(1)
        main.addLayout(bar)
        self.status = QLabel("Aguardando arquivo de telemetria local")
        self.status.setObjectName("infoLabel")
        main.addWidget(self.status)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        main.addWidget(self.table, 1)
        self.file.editingFinished.connect(self._save)
        self.auto.toggled.connect(self._save)

    def _browse(self):
        pattern = "Arquivos JSON (*.json)" if self.kind != "AIS" else "AIS NMEA (*.nmea *.txt *.log);;Todos (*.*)"
        name, _ = QFileDialog.getOpenFileName(self, "Arquivo de telemetria", self.file.text(), pattern)
        if name:
            self.file.setText(name)
            self._save()
            self.refresh(force=True)

    def _save(self, *_):
        key = "traffic_" + self.kind.lower()
        self.cfg[key + "_path"] = self.file.text().strip()
        self.cfg[key + "_auto"] = self.auto.isChecked()
        self.cfg.save()
        self.last_stamp = None

    def refresh(self, force=False):
        name = self.file.text().strip()
        if not name:
            return
        try:
            p = Path(name).expanduser()
            # mtime_ns + tamanho permite distinguir saídas regeneradas com o mesmo segundo.
            st = p.stat()
            stamp = (st.st_mtime_ns, st.st_size)
            if not force and stamp == self.last_stamp:
                return
            records = load_traffic(p, self.kind)
            self.last_stamp = stamp
        except (OSError, ValueError, UnicodeError) as exc:
            self.status.setText(f"Falha na leitura: {exc}")
            return
        self.records = records
        self._add_history(records)
        self._populate(records)
        self.status.setText(f"{len(records)} posições válidas de {p.name}. "
                            "A atualização depende do decodificador externo.")

    def _add_history(self, positions):
        for point in positions:
            last = next((x for x in reversed(self.history)
                         if x.source == point.source and x.ident == point.ident), None)
            if last and abs(last.lat - point.lat) < 0.00001 and abs(last.lon - point.lon) < 0.00001:
                continue
            self.history.append(point)
        self.history = self.history[-5000:]

    def add_live_record(self, record):
        self._add_history([record])
        self.records = [record] + [x for x in self.records if x.ident != record.ident][:499]
        self._populate(self.records)
        self.status.setText(f"{len(self.records)} posições de sondas meteorológicas")

    def _populate(self, records):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(min(len(records), 500))
        for row, record in enumerate(records[:500]):
            values = (record.ident, record.label, f"{record.lat:.5f}", f"{record.lon:.5f}",
                      "" if record.altitude_m is None else f"{record.altitude_m:.0f}",
                      "" if record.speed_kmh is None else f"{record.speed_kmh:.1f}",
                      "" if record.course_deg is None else f"{record.course_deg:.1f}",
                      "" if record.vertical_ms is None else f"{record.vertical_ms:.1f}",
                      record.details, time.strftime("%d/%m %H:%M:%S", time.localtime(record.timestamp)))
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.setSortingEnabled(True)

    def open_map(self):
        if not self.records:
            QMessageBox.information(self, "Mapa", "Nenhuma posição válida para exibir.")
            return
        try:
            path = export_map(self.history or self.records, config_dir() / ("mapa_" + self.kind.lower().replace("-", "_") + ".html"))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except OSError as exc:
            QMessageBox.warning(self, "Mapa", str(exc))

    def _export_tracks(self):
        if not self.history and not self.records:
            QMessageBox.information(self, "Exportação", "Sem trajetórias para exportar.")
            return
        filename, selected = QFileDialog.getSaveFileName(
            self, "Exportar trilhas", self.kind.lower() + ".gpx",
            "GPX (*.gpx);;KML (*.kml)")
        if not filename:
            return
        try:
            if filename.lower().endswith(".kml") or "KML" in selected:
                export_kml(self.history or self.records, filename)
            else:
                export_gpx(self.history or self.records, filename)
        except OSError as exc:
            QMessageBox.warning(self, "Exportação", str(exc))

    def _export(self):
        if not self.records:
            QMessageBox.information(self, "Exportação", "Nenhum registro para exportar.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", self.kind.lower() + ".csv", "CSV (*.csv)")
        if p:
            try:
                export_csv(self.records, p)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Exportação", str(exc))


class TrafficFeedsPanel(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.tabs = QTabWidget()
        self.sources = {}
        outer = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        all_map = QPushButton("Mapa unificado (OpenStreetMap)")
        all_map.clicked.connect(self.open_map)
        all_refresh = QPushButton("Atualizar todas as fontes")
        all_refresh.clicked.connect(self.refresh_all)
        toolbar.addWidget(all_map)
        toolbar.addWidget(all_refresh)
        toolbar.addStretch(1)
        outer.addLayout(toolbar)
        outer.addWidget(self.tabs, 1)
        for kind, title in (("ADS-B", "Aviões · 1090 MHz"), ("AIS", "Navios · 162 MHz"),
                            ("Sonda", "Radiossondas · 400 MHz")):
            tab = SourceTab(kind, cfg)
            self.sources[kind] = tab
            self.tabs.addTab(tab, title)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_auto)
        self.timer.start()

    def refresh_auto(self):
        for tab in self.sources.values():
            if tab.auto.isChecked():
                tab.refresh()

    def refresh_all(self):
        for tab in self.sources.values():
            tab.refresh(force=True)

    def open_map(self):
        positions = [p for tab in self.sources.values() for p in tab.records]
        if not positions:
            QMessageBox.information(self, "Mapa de tráfego", "Nenhuma posição recebida. Configure e atualize as fontes.")
            return
        try:
            path = export_map(positions, config_dir() / "mapa_trafego_sdr.html")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except OSError as exc:
            QMessageBox.warning(self, "Mapa de tráfego", f"Erro ao gerar mapa: {exc}")
