"""Configuração compartilhada dos testes, inclusive ciclo de vida do Qt offscreen."""
import gc
import os

import pytest

# Mantém o wrapper Python do QApplication vivo durante a finalização do PySide6.
_QT_SESSION_APP = None

# Os testes não podem abrir diálogos modais de abertura (anúncio do site / resultado de atualização).
os.environ["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PT2VHF_NO_AUTOCONNECT"] = "1"


@pytest.fixture(scope="session", autouse=True)
def qt_lifecycle():
    """Mantém uma única QApplication viva durante toda a suíte.

    PySide6 pode sofrer falha nativa na saída do interpretador se cada teste
    deixar destruir/recriar QApplication enquanto gráficos Qt continuam pendentes.
    """
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    global _QT_SESSION_APP
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    _QT_SESSION_APP = app
    yield app
    QApplication.closeAllWindows()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    for w in list(QApplication.topLevelWidgets()):
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()
