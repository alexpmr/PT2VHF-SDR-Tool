"""Fontes de rede e genéricas: rtl_tcp e SoapySDR (Airspy, HackRF, SDRplay, LimeSDR...)."""
from __future__ import annotations

import logging
import socket
import struct

import numpy as np

from .base import IQSource, SourceError, u8_to_complex

log = logging.getLogger(__name__)

RTL_TCP_TUNERS = {1: "E4000", 2: "FC0012", 3: "FC0013", 4: "FC2580", 5: "R820T", 6: "R828D"}


class RtlTcpSource(IQSource):
    """Cliente do protocolo rtl_tcp (servidor RTL-SDR remoto em rede)."""

    name = "rtl_tcp"
    supports_gain = True
    supports_ppm = True
    supports_bias_tee = True
    supports_direct_sampling = True
    gains_db = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7,
                22.9, 25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4,
                43.9, 44.5, 48.0, 49.6]

    def __init__(self, sample_rate: int, center_freq: float, host: str = "127.0.0.1",
                 port: int = 1234, gain=None, ppm: int = 0):
        super().__init__(sample_rate, center_freq)
        try:
            self.sock = socket.create_connection((host, int(port)), timeout=5)
        except OSError as e:
            raise SourceError(f"Não foi possível conectar a {host}:{port}: {e}") from e
        hdr = self._recv_exact(12)
        if hdr[:4] != b"RTL0":
            raise SourceError("Servidor não respondeu com cabeçalho rtl_tcp")
        tuner, _ngains = struct.unpack(">II", hdr[4:])
        self.tuner = RTL_TCP_TUNERS.get(tuner, "desconhecido")
        self.direct_sampling = 0
        self.sock.settimeout(2)
        self._cmd(0x02, self.sample_rate)
        self._cmd(0x01, int(center_freq))
        self.set_ppm(ppm)
        self.set_gain(gain)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise SourceError("Conexão rtl_tcp encerrada")
            buf += chunk
        return buf

    def _cmd(self, cmd: int, param: int):
        self.sock.sendall(struct.pack(">BI", cmd, param & 0xFFFFFFFF))

    def _run(self):
        nbytes = self.block_size * 2
        buf = bytearray()
        while self._running:
            try:
                chunk = self.sock.recv(262144)
            except socket.timeout:
                continue
            except OSError as e:
                log.error("rtl_tcp: %s", e)
                break
            if not chunk:
                break
            buf += chunk
            while len(buf) >= nbytes:
                self._push(u8_to_complex(bytes(buf[:nbytes])))
                del buf[:nbytes]
        self._running = False

    def check_freq(self, hz):
        from .rtlsdr_source import tuning_range
        if self.tuner == "desconhecido":
            return "Sintonizador rtl_tcp não identificado."
        lo, hi = tuning_range(self.tuner, False, self.direct_sampling)
        return "" if lo <= hz <= hi else f"rtl_tcp ({self.tuner}): fora de {lo / 1e6:g}–{hi / 1e6:g} MHz."

    def set_center_freq(self, hz):
        problem = self.check_freq(hz)
        if problem:
            raise SourceError(problem)
        super().set_center_freq(hz)
        self._cmd(0x01, int(hz))

    def set_gain(self, db):
        if db is None:
            self._cmd(0x03, 0)
            self._cmd(0x08, 1)
        else:
            self._cmd(0x03, 1)
            self._cmd(0x04, int(round(db * 10)))

    def set_ppm(self, ppm):
        self._cmd(0x05, int(ppm))

    def set_bias_tee(self, on):
        self._cmd(0x0E, 1 if on else 0)

    def set_direct_sampling(self, mode):
        self._cmd(0x09, int(mode))
        self.direct_sampling = int(mode)

    def close(self):
        super().close()
        try:
            self.sock.close()
        except OSError:
            pass


def soapy_devices() -> list[str]:
    try:
        import SoapySDR  # noqa: N813
        return [",".join(f"{k}={v}" for k, v in dict(d).items()) for d in SoapySDR.Device.enumerate()]
    except Exception:  # noqa: BLE001
        return []


class SoapySource(IQSource):
    """Qualquer receptor suportado pelo SoapySDR (requer instalação do SoapySDR + módulos)."""

    name = "SoapySDR"
    supports_gain = True
    supports_ppm = True

    def __init__(self, sample_rate: int, center_freq: float, args: str = "", gain=None, ppm: int = 0):
        super().__init__(sample_rate, center_freq)
        try:
            import SoapySDR
            from SoapySDR import SOAPY_SDR_CF32, SOAPY_SDR_RX
        except Exception as e:  # noqa: BLE001
            raise SourceError(f"SoapySDR não instalado: {e}") from e
        self._soapy = SoapySDR
        self._rx = SOAPY_SDR_RX
        self.dev = SoapySDR.Device(args)
        self.dev.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
        self.dev.setFrequency(SOAPY_SDR_RX, 0, center_freq)
        self.frequency_ranges = []
        for freq_range in self.dev.getFrequencyRange(SOAPY_SDR_RX, 0):
            self.frequency_ranges.append((float(freq_range.minimum()),
                                          float(freq_range.maximum())))
        rng = self.dev.getGainRange(SOAPY_SDR_RX, 0)
        self.gains_db = [float(g) for g in np.arange(rng.minimum(), rng.maximum() + 0.1, 1.0)]
        self.set_gain(gain)
        self.set_ppm(ppm)
        self.stream = self.dev.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)

    def _run(self):
        self.dev.activateStream(self.stream)
        buf = np.empty(self.block_size, np.complex64)
        while self._running:
            got = 0
            while got < self.block_size and self._running:
                sr = self.dev.readStream(self.stream, [buf[got:]], self.block_size - got, timeoutUs=500000)
                if sr.ret > 0:
                    got += sr.ret
            if got:
                self._push(buf[:got].copy())
        self.dev.deactivateStream(self.stream)

    def check_freq(self, hz):
        if any(lo <= hz <= hi for lo, hi in self.frequency_ranges):
            return ""
        return ("SoapySDR: faixa de sintonia não identificada." if not self.frequency_ranges
                else f"SoapySDR: {hz / 1e6:g} MHz fora das faixas do dispositivo.")

    def set_center_freq(self, hz):
        problem = self.check_freq(hz)
        if problem:
            raise SourceError(problem)
        super().set_center_freq(hz)
        self.dev.setFrequency(self._rx, 0, hz)

    def set_gain(self, db):
        if db is None:
            try:
                self.dev.setGainMode(self._rx, 0, True)
            except Exception:  # noqa: BLE001
                pass
        else:
            try:
                self.dev.setGainMode(self._rx, 0, False)
            except Exception:  # noqa: BLE001
                pass
            self.dev.setGain(self._rx, 0, db)

    def set_ppm(self, ppm):
        try:
            self.dev.setFrequencyCorrection(self._rx, 0, ppm)
        except Exception:  # noqa: BLE001
            pass

    def close(self):
        super().close()
        try:
            self.dev.closeStream(self.stream)
        except Exception:  # noqa: BLE001
            pass
