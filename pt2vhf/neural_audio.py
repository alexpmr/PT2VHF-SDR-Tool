"""RNNoise neural para fonia demodulada, fora da thread DSP e sem rede.

Entrada/saída: PCM mono float32 48 kHz. A biblioteca pyrnnoise usa 480
amostras por quadro; o backlog é limitado para não travar a recepção SDR.
Modos digitais, WFM e CW são encaminhados sem RNNoise para não degradar dados
ou música. A filtragem nunca é aplicada ao IQ nem aos decodificadores RF.
"""
from __future__ import annotations

import importlib.util
import logging
import queue
import threading
from collections.abc import Callable

import numpy as np

log = logging.getLogger(__name__)
FRAME = 480
VOICE_MODES = frozenset(("NFM", "AM", "USB", "LSB", "DSB"))


def backend_available() -> bool:
    try:
        return importlib.util.find_spec("pyrnnoise") is not None
    except (ImportError, ValueError):
        return False


class NeuralAudioWorker:
    """Pipeline assíncrono de áudio: RF jamais espera a inferência da RNN.

    on_audio recebe áudio tratado (ou original se não houver modo de voz).
    Um excesso de CPU descarta o bloco mais antigo, não acumula segundos
    de áudio atrasado na placa de som e registra o número de perdas.
    """

    def __init__(self, on_audio: Callable, on_error: Callable | None = None,
                 strength: float = 0.8, backend=None, max_pending: int = 8):
        self.on_audio = on_audio
        self.on_error = on_error
        self.strength = max(0.0, min(1.0, float(strength)))
        self.dropped = 0
        self.processed_frames = 0
        self._backend = backend
        self._tail = np.empty(0, np.float32)
        self._tasks: queue.Queue = queue.Queue(maxsize=max_pending)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="rnnoise-audio")
        self._thread.start()

    @property
    def queue_depth(self) -> int:
        return self._tasks.qsize()

    def feed(self, audio, mode="NFM"):
        if self._stop.is_set():
            return False
        chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not chunk.size:
            return True
        item = (chunk.copy(), mode in VOICE_MODES)
        try:
            self._tasks.put_nowait(item)
        except queue.Full:
            try:
                self._tasks.get_nowait()
                self.dropped += 1
                self._tasks.put_nowait(item)
            except queue.Empty:
                self.dropped += 1
                return False
        return True

    def _get_backend(self):
        if self._backend is None:
            from pyrnnoise import RNNoise
            self._backend = RNNoise(sample_rate=48000)
        return self._backend

    def _enhance(self, audio: np.ndarray, backend) -> np.ndarray:
        data = np.concatenate((self._tail, audio))
        frames = (data.size // FRAME) * FRAME
        self._tail = data[frames:].copy()
        if not frames:
            return np.empty(0, np.float32)
        pcm = np.round(np.clip(data[:frames], -1, 1) * 32767).astype(np.int16)
        cleaned = []
        # API pública: shape [canais, amostras], retorna quadros de 480.
        for _speech_prob, output in backend.denoise_chunk(pcm.reshape(1, -1)):
            arr = np.asarray(output).reshape(-1)
            if np.issubdtype(arr.dtype, np.integer):
                arr = arr.astype(np.float32) / 32768.0
            else:
                arr = arr.astype(np.float32)
            cleaned.append(arr)
        if not cleaned:
            return data[:frames].astype(np.float32)  # falha não gera áudio mudo
        result = np.concatenate(cleaned)
        if len(result) != frames:
            # Manter clocks e ordem: backend incompatível nunca altera o tempo.
            raise RuntimeError(f"RNNoise retornou {len(result)} amostras para {frames}")
        self.processed_frames += frames // FRAME
        return np.clip(
            self.strength * result + (1.0 - self.strength) * data[:frames], -1.0, 1.0
        ).astype(np.float32)

    def _run(self):
        backend = None
        try:
            backend = self._get_backend()
        except Exception as ex:  # noqa: BLE001
            log.warning("RNNoise não pôde iniciar: %s", ex)
            if self.on_error:
                self.on_error(f"RNNoise indisponível: {ex}")
        while not self._stop.is_set():
            try:
                item = self._tasks.get(timeout=0.15)
            except queue.Empty:
                continue
            if item is None:
                break
            audio, voice = item
            if backend is None or not voice:
                if self._tail.size:
                    audio = np.concatenate((self._tail, audio))
                    self._tail = np.empty(0, np.float32)
                result = audio
            else:
                try:
                    result = self._enhance(audio, backend)
                except Exception as ex:  # noqa: BLE001
                    log.warning("RNNoise: falha no processamento: %s", ex)
                    if self.on_error:
                        self.on_error(f"Falha na redução neural: {ex}")
                    # Fallback: nunca silenciar áudio após erro no plugin.
                    result = audio.copy()
                    self._tail = np.empty(0, np.float32)
                    backend = None
            if result.size and not self._stop.is_set():
                try:
                    self.on_audio(result)
                except Exception:  # noqa: BLE001
                    log.exception("Falha na entrega do áudio RNNoise")

    def stop(self):
        self._stop.set()
        try:
            self._tasks.put_nowait(None)
        except queue.Full:
            pass
