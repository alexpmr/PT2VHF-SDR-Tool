"""Interface comum para fontes de IQ (RTL-SDR, rtl_tcp, SoapySDR, arquivo, simulador)."""
from __future__ import annotations

import queue
import threading

import numpy as np


class SourceError(Exception):
    pass


class IQSource:
    """Classe base. As subclasses entregam blocos complex64 por `read()`.

    Fontes de hardware rodam uma thread de leitura que preenche uma fila,
    evitando perder amostras enquanto a cadeia DSP processa.
    """

    name = "Base"
    tunable = True  # False = frequência central fixa (ex.: gravação IQ)
    supports_gain = False
    supports_ppm = False
    supports_bias_tee = False
    supports_direct_sampling = False
    gains_db: list[float] = []

    def __init__(self, sample_rate: int, center_freq: float):
        self.sample_rate = int(sample_rate)
        self.center_freq = float(center_freq)
        self.block_size = self._choose_block(self.sample_rate)
        self._q: queue.Queue = queue.Queue(maxsize=32)
        self._running = False
        self._thread: threading.Thread | None = None
        self.dropped = 0

    @staticmethod
    def _choose_block(fs: int) -> int:
        # ~20 blocos/s, múltiplo de 16384 (requisito do librtlsdr: múltiplo de 512 bytes)
        n = int(fs / 20)
        return max(16384, (n // 16384) * 16384)

    # ---- ciclo de vida
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"src-{self.name}")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self):  # pragma: no cover - implementado nas subclasses
        raise NotImplementedError

    def _push(self, block: np.ndarray):
        try:
            self._q.put_nowait(block)
        except queue.Full:
            self.dropped += 1
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            self._q.put_nowait(block)

    def read(self, timeout: float = 0.5) -> np.ndarray | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    # ---- controles (padrão: sem efeito)
    def set_center_freq(self, hz: float):
        self.center_freq = float(hz)

    def check_freq(self, hz: float) -> str:
        """'' se a fonte alcança a frequência; senão, explicação para o usuário."""
        return ""

    def set_gain(self, db: float | None):
        """None = AGC do sintonizador."""

    def set_ppm(self, ppm: int):
        pass

    def set_bias_tee(self, on: bool):
        pass

    def set_direct_sampling(self, mode: int):
        pass

    def close(self):
        self.stop()


def u8_to_complex(buf: bytes | np.ndarray) -> np.ndarray:
    a = np.frombuffer(buf, dtype=np.uint8).astype(np.float32)
    a = (a - 127.4) / 128.0
    return (a[0::2] + 1j * a[1::2]).astype(np.complex64)
