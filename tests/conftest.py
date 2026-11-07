import os

# Os testes não podem abrir diálogos modais de abertura (anúncio do site / resultado de atualização).
os.environ["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PT2VHF_NO_AUTOCONNECT"] = "1"
