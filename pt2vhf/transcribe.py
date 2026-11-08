"""Transcrição local (opcional) das transmissões gravadas.

Usa o pacote `faster-whisper` se estiver instalado (o modelo roda no próprio computador,
sem enviar áudio para a internet). Sem ele, o recurso fica indisponível e nada muda no programa.
"""
from __future__ import annotations

import logging
import queue
import re
import threading

log = logging.getLogger(__name__)

# Indicativos: prefixo (1–2 letras e/ou dígito), um dígito, sufixo de 1–4 letras. Ex.: PY2ABC, PT2VHF, K1ABC
CALLSIGN_RE = re.compile(r"\b(?:[A-Z]{1,2}[0-9]|[0-9][A-Z])[0-9]?[A-Z]{1,4}\b")


def find_callsigns(text: str) -> list[str]:
    found = []
    for m in CALLSIGN_RE.findall(text.upper()):
        if any(c.isdigit() for c in m) and m not in found:
            found.append(m)
    return found


def backend_available() -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        return False


class Transcriber:
    """Fila de transcrição em segundo plano. `on_result(path, text, callsigns)` é chamado na thread."""

    def __init__(self, on_result, model_size: str = "small", language: str = "pt", model=None):
        self.on_result = on_result
        self.model_size = model_size
        self.language = language
        self._model = model  # permite injetar um modelo (testes)
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="transcricao")
        self._thread.start()
        self.error = ""

    def submit(self, path: str):
        self._q.put(path)

    def stop(self):
        self._q.put(None)

    def _load(self):
        if self._model is None:
            from .live_caption import model_installed, local_model_path
            if not model_installed(self.model_size):
                raise FileNotFoundError("Baixe o modelo Whisper na aba Scanner > Legendas ao vivo.")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(str(local_model_path(self.model_size)),
                                       device="cpu", compute_type="int8",
                                       local_files_only=True)
        return self._model

    def _run(self):
        while True:
            path = self._q.get()
            if path is None:
                return
            try:
                model = self._load()
                segments, _info = model.transcribe(path, language=self.language, vad_filter=True)
                text = " ".join(s.text.strip() for s in segments).strip()
            except Exception as e:  # noqa: BLE001
                self.error = str(e)
                log.warning("Transcrição falhou: %s", e)
                text = ""
            self.on_result(path, text, find_callsigns(text))
