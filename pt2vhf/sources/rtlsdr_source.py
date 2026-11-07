"""Fonte RTL-SDR local (USB) via pyrtlsdr/librtlsdr."""
from __future__ import annotations

import logging

import numpy as np

from .base import IQSource, SourceError

log = logging.getLogger(__name__)


def list_devices() -> list[str]:
    """Lista os dongles RTL-SDR conectados (vazio se a biblioteca não estiver instalada)."""
    try:
        from rtlsdr.librtlsdr import librtlsdr
        n = librtlsdr.rtlsdr_get_device_count()
        return [f"{i}: {librtlsdr.rtlsdr_get_device_name(i).decode(errors='replace')}"
                for i in range(n)]
    except Exception as e:  # noqa: BLE001
        log.info("RTL-SDR indisponível: %s", e)
        return []


class RtlSdrSource(IQSource):
    name = "RTL-SDR"
    supports_gain = True
    supports_ppm = True
    supports_bias_tee = True
    supports_direct_sampling = True

    def __init__(self, sample_rate: int, center_freq: float, device_index: int = 0,
                 gain: float | None = None, ppm: int = 0):
        super().__init__(sample_rate, center_freq)
        try:
            from rtlsdr import RtlSdr
        except Exception as e:  # noqa: BLE001
            raise SourceError(
                "Biblioteca librtlsdr não encontrada. Instale 'pyrtlsdr[lib]' e o driver "
                f"WinUSB com o Zadig.\nDetalhe: {e}") from e
        try:
            self.sdr = RtlSdr(device_index)
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"Não foi possível abrir o RTL-SDR #{device_index}: {e}") from e
        self.sdr.sample_rate = self.sample_rate
        self.sdr.center_freq = int(center_freq)
        try:
            self.gains_db = [g / 10 for g in self.sdr.get_gains()]
        except Exception:  # noqa: BLE001
            self.gains_db = list(getattr(self.sdr, "valid_gains_db", []))
        self.set_ppm(ppm)
        self.set_gain(gain)

    def _run(self):
        def cb(samples, _ctx):
            if not self._running:
                self.sdr.cancel_read_async()
                return
            self._push(np.asarray(samples, dtype=np.complex64))
        try:
            self.sdr.read_samples_async(cb, self.block_size)
        except Exception as e:  # noqa: BLE001
            log.error("Erro de leitura RTL-SDR: %s", e)
            self._running = False

    def stop(self):
        if self._running:
            self._running = False
            try:
                self.sdr.cancel_read_async()
            except Exception:  # noqa: BLE001
                pass
        super().stop()

    def set_center_freq(self, hz: float):
        super().set_center_freq(hz)
        self.sdr.center_freq = int(hz)

    def set_gain(self, db):
        if db is None:
            self.sdr.gain = "auto"
        else:
            self.sdr.gain = float(db)

    def set_ppm(self, ppm: int):
        try:
            if int(ppm) != 0 or self.sdr.freq_correction != 0:
                self.sdr.freq_correction = int(ppm)
        except Exception:  # noqa: BLE001  (librtlsdr retorna erro se o valor não muda)
            pass

    def set_bias_tee(self, on: bool):
        try:
            self.sdr.set_bias_tee(bool(on))
        except Exception as e:  # noqa: BLE001
            log.warning("Bias-T não suportado: %s", e)

    def set_direct_sampling(self, mode: int):
        """0 = desligado, 1 = ramo I, 2 = ramo Q (RTL-SDR Blog V3/V4 em HF)."""
        try:
            self.sdr.set_direct_sampling(int(mode))
        except Exception as e:  # noqa: BLE001
            log.warning("Amostragem direta não suportada: %s", e)

    def close(self):
        self.stop()
        try:
            self.sdr.close()
        except Exception:  # noqa: BLE001
            pass
