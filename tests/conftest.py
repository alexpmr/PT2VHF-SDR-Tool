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
    from PySide6.QtWidgets import QApplication

    global _QT_SESSION_APP
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    _QT_SESSION_APP = app
    yield app
    # Não forçar DeferredDelete durante o shutdown: widgets Qt (pyqtgraph)
    # podem manter callbacks/itens C++ pendentes até o fim da sessão.
    # Fechamos janelas, processamos eventos e mantemos QApplication viva.
    # Diagnostic-only A/B probe. Default preserves the existing teardown.
    # Never enable this outside experimental Windows CI investigations.
    mode = os.environ.get("PT2VHF_QT_TEST_TEARDOWN", "baseline")
    if mode == "skip":
        return
    if mode != "baseline":
        raise ValueError("PT2VHF_QT_TEST_TEARDOWN must be baseline or skip")
    QApplication.closeAllWindows()
    app.processEvents()
    gc.collect()
