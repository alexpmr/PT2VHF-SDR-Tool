"""Ponto de entrada da aplicação."""
from __future__ import annotations

import argparse
import logging
import sys


def main():
    ap = argparse.ArgumentParser(description="PT2VHF SDR Tool")
    ap.add_argument("--debug", action="store_true", help="log detalhado")
    ap.add_argument("--sim", action="store_true", help="liga o simulador ao iniciar")
    ap.add_argument("--screenshot", metavar="PNG", help="(teste) salva captura de tela e sai")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("PT2VHF")
    w = MainWindow()
    w.show()
    if args.sim or args.screenshot:
        w.rx_panel.source.setCurrentText("Simulador")
        w.rx_panel.start_btn.setChecked(True)
    if args.screenshot:
        def shot():
            w._auto_levels()
            QTimer.singleShot(1500, lambda: (w.grab().save(args.screenshot), app.quit()))
        QTimer.singleShot(int(10_000), shot)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
