"""Indicador compacto CPU/RAM do processo no cabeçalho PT2VHF."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..resource_monitor import ProcessResourceSampler


class ResourceMeter(QFrame):
    """Duas linhas, inspirado no medidor CPU/RAM fornecido pelo usuário."""

    def __init__(self, parent: QWidget | None = None, *, sampler=None):
        super().__init__(parent)
        self.setObjectName("resourceMeter")
        self.setFixedSize(109, 44)
        self.setToolTip(
            "Consumo do PT2VHF SDR Tool (não do computador inteiro). "
            "CPU: percentual da capacidade total dos núcleos lógicos. "
            "RAM: memória residente em MB (pico no macOS)."
        )
        self.setStyleSheet("""
            QFrame#resourceMeter {
                background:#0d171f; border:1px solid #2a5261;
                border-radius:5px;
            }
            QLabel { background:transparent; border:none; }
            QLabel#resourceMetric {
                color:#61c7e6; font:bold 9px 'Segoe UI';
            }
            QLabel#resourceValue {
                color:#f1f6ff; font:bold 10px 'Segoe UI';
            }
            QLabel#resourceDot { color:#32c887; font-size:8px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(1)
        self.cpu_value = self._line(layout, "CPU", "resourceCpuValue", "—")
        self.ram_value = self._line(layout, "RAM", "resourceRamValue", "—")
        self._sampler = sampler or ProcessResourceSampler()
        # UI remains responsive: one process CPU clock read and one local RSS
        # query every 2 seconds; no worker thread and no network traffic.
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    @staticmethod
    def _line(layout: QVBoxLayout, title: str, value_name: str, initial: str) -> QLabel:
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(3)
        dot = QLabel("●")
        dot.setObjectName("resourceDot")
        dot.setFixedWidth(7)
        line.addWidget(dot)
        name = QLabel(title)
        name.setObjectName("resourceMetric")
        line.addWidget(name)
        line.addStretch(1)
        value = QLabel(initial)
        value.setObjectName(value_name)
        # The same common label styling is applied by object name.
        value.setStyleSheet("color:#f1f6ff; background:transparent; border:none;"
                            "font:bold 10px 'Segoe UI';")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        line.addWidget(value)
        layout.addLayout(line)
        return value

    def refresh(self):
        cpu, ram = self._sampler.sample()
        self.cpu_value.setText("—" if cpu is None else f"{cpu:.1f}%")
        self.ram_value.setText("—" if ram is None else f"{round(ram / 1048576)} MB")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
