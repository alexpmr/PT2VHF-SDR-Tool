"""Fonte RTL-SDR local (USB) via pyrtlsdr/librtlsdr — robusta contra travamentos.

Regras (v0.4.0):
- a interface nunca chama a librtlsdr: os ajustes entram numa fila e uma thread de controle os aplica,
  com tempo limite; se o dongle não responde, o problema é informado e a janela continua livre;
- a leitura é assíncrona; um vigia percebe quando as amostras param (erro de USB/sintonizador),
  reabre o dispositivo, reaplica frequência/ganho/ppm/bias-T e retoma sozinho;
- frequência fora do alcance do dongle é recusada com aviso, mantendo a anterior;
- no Windows usa, quando incluída no pacote, a biblioteca do driver RTL-SDR Blog (suporte ao V4, HF pelo
  upconverter interno).
"""
from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np

from .base import IQSource, SourceError

log = logging.getLogger(__name__)

_LIB_INFO = {"name": "", "blog": False}


def _bundled_blog_dir() -> Path | None:
    roots = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).resolve().parent,
             Path(__file__).resolve().parents[2] / "packaging"]
    for r in roots:
        d = r / "rtlsdr_blog"
        if (d / "rtlsdr.dll").is_file():
            return d
    return None


def load_library():
    """Carrega a librtlsdr (preferindo a do driver RTL-SDR Blog quando incluída). Retorna o módulo."""
    if "rtlsdr.librtlsdr" in sys.modules:
        return sys.modules["rtlsdr.librtlsdr"].librtlsdr
    blog = _bundled_blog_dir() if sys.platform == "win32" else None
    if blog is not None:
        try:
            os.add_dll_directory(str(blog))
            os.environ["PATH"] = str(blog) + os.pathsep + os.environ.get("PATH", "")
            import ctypes
            for dep in ("msvcr100.dll", "libusb-1.0.dll", "pthreadVC2.dll"):
                if (blog / dep).is_file():
                    ctypes.CDLL(str(blog / dep))
            ctypes.CDLL(str(blog / "rtlsdr.dll"))
            sys.modules["pyrtlsdrlib"] = None  # força o pyrtlsdr a usar a DLL do driver Blog
        except OSError as e:
            log.warning("Biblioteca RTL-SDR Blog não carregou (%s); usando a padrão", e)
            sys.modules.pop("pyrtlsdrlib", None)
    from rtlsdr.librtlsdr import librtlsdr
    _LIB_INFO["name"] = getattr(librtlsdr, "_name", "") or ""
    try:
        getattr(librtlsdr, "rtlsdr_set_dithering")  # só existe no driver RTL-SDR Blog
        _LIB_INFO["blog"] = True
    except AttributeError:
        _LIB_INFO["blog"] = False
    return librtlsdr


def library_info() -> dict:
    try:
        load_library()
    except Exception as e:  # noqa: BLE001
        return {"name": "", "blog": False, "error": str(e)}
    return dict(_LIB_INFO)


def list_devices() -> list[str]:
    """Lista os dongles RTL-SDR conectados (vazio se a biblioteca não estiver disponível)."""
    try:
        lib = load_library()
        n = lib.rtlsdr_get_device_count()
        return [f"{i}: {lib.rtlsdr_get_device_name(i).decode(errors='replace')}" for i in range(n)]
    except Exception as e:  # noqa: BLE001
        log.info("RTL-SDR indisponível: %s", e)
        return []


def tuning_range(tuner: str, blog_lib: bool, direct_sampling: int, product: str = "") -> tuple[float, float]:
    """Faixa sintonizável (Hz) conforme o sintonizador e a biblioteca."""
    if direct_sampling:
        return 500e3, 28.8e6
    t = (tuner or "").upper()
    if "E4000" in t:
        return 52e6, 2200e6
    if "FC0012" in t or "FC0013" in t:
        return 22e6, 1100e6
    if "FC2580" in t:
        return 146e6, 924e6
    if "R828D" in t and blog_lib and ("V4" in product.upper() or "BLOG" in product.upper()):
        return 500e3, 1766e6  # RTL-SDR Blog V4: HF pelo upconverter interno
    return 24e6, 1766e6       # R820T/R828D


class RtlSdrSource(IQSource):
    name = "RTL-SDR"
    supports_gain = True
    supports_ppm = True
    supports_bias_tee = True
    supports_direct_sampling = True
    STALL_S = 2.0          # sem amostras por este tempo = fluxo parado
    CMD_TIMEOUT_S = 3.0    # comando que não volta = dongle sem resposta
    MAX_RECOVER = 3

    def __init__(self, sample_rate: int, center_freq: float, device_index: int = 0,
                 gain: float | None = None, ppm: int = 0, sdr_factory=None):
        super().__init__(sample_rate, center_freq)
        self.device_index = device_index
        self.gain = gain
        self.ppm = int(ppm)
        self.bias_tee = False
        self.direct_sampling = 0
        self.status = "ok"           # ok | recovering | failed
        self.message = ""            # última mensagem para a interface (lida pelo motor)
        self._messages: queue.Queue = queue.Queue()
        self._factory = sdr_factory or self._default_factory
        self._ctl: queue.Queue = queue.Queue()
        self._last_block = 0.0
        self._reader: threading.Thread | None = None
        self._ctl_thread: threading.Thread | None = None
        self._watch_thread: threading.Thread | None = None
        self._busy_since = 0.0
        self._recovering = threading.Lock()
        self.sdr = self._open()
        self.tuner = self._tuner_name()
        self.product = self._product_name()
        self.range = tuning_range(self.tuner, library_info().get("blog", False), 0, self.product)

    # ------------------------------------------------------------ abertura
    def _default_factory(self, index: int):
        try:
            load_library()
            from rtlsdr import RtlSdr
        except Exception as e:  # noqa: BLE001
            raise SourceError("Biblioteca librtlsdr não encontrada. Reinstale o PT2VHF SDR Tool.\n"
                              f"Detalhe: {e}") from e
        return RtlSdr(index)

    def _open(self):
        try:
            sdr = self._factory(self.device_index)
        except SourceError:
            raise
        except Exception as e:  # noqa: BLE001
            raise SourceError(
                f"Não foi possível abrir o RTL-SDR #{self.device_index}: {e}\n\n"
                "Se for a primeira vez, use Ajuda → Preparar RTL-SDR (instala o driver WinUSB) "
                "ou o Zadig, e reconecte o dongle.") from e
        sdr.sample_rate = self.sample_rate
        try:
            sdr.center_freq = int(self.center_freq)
        except Exception:  # noqa: BLE001  frequência salva fora do alcance: abre em 2 m
            self.center_freq = 145.5e6
            sdr.center_freq = int(self.center_freq)
            self._messages.put("A frequência anterior está fora do alcance deste RTL-SDR; abrindo em 145,5 MHz.")
        self._apply_settings(sdr)
        return sdr

    def _apply_settings(self, sdr):
        for fn in (lambda: setattr(sdr, "gain", "auto" if self.gain is None else float(self.gain)),
                   lambda: setattr(sdr, "freq_correction", int(self.ppm)) if self.ppm else None,
                   lambda: sdr.set_bias_tee(bool(self.bias_tee)) if self.bias_tee else None,
                   lambda: sdr.set_direct_sampling(int(self.direct_sampling)) if self.direct_sampling else None):
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                log.debug("ajuste ignorado: %s", e)
        try:
            self.gains_db = [g / 10 for g in sdr.get_gains()]
        except Exception:  # noqa: BLE001
            self.gains_db = list(getattr(sdr, "valid_gains_db", []))

    def _tuner_name(self) -> str:
        try:
            t = self.sdr.get_tuner_type()
            names = {1: "E4000", 2: "FC0012", 3: "FC0013", 4: "FC2580", 5: "R820T", 6: "R828D"}
            return names.get(int(t), str(t))
        except Exception:  # noqa: BLE001
            return ""

    def _product_name(self) -> str:
        try:
            from rtlsdr.librtlsdr import librtlsdr
            import ctypes
            m, p, s = (ctypes.create_string_buffer(256) for _ in range(3))
            librtlsdr.rtlsdr_get_device_usb_strings(self.device_index, m, p, s)
            return f"{m.value.decode(errors='replace')} {p.value.decode(errors='replace')}".strip()
        except Exception:  # noqa: BLE001
            return ""

    def _say(self, msg: str):
        self.message = msg
        self._messages.put(msg)
        log.warning(msg)

    def pop_messages(self) -> list[str]:
        out = []
        while True:
            try:
                out.append(self._messages.get_nowait())
            except queue.Empty:
                return out

    # ------------------------------------------------------------ ciclo de vida
    def start(self):
        self._running = True
        self._last_block = time.monotonic()
        self._start_reader()
        self._ctl_thread = threading.Thread(target=self._control_loop, daemon=True, name="rtl-ctl")
        self._ctl_thread.start()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True, name="rtl-watch")
        self._watch_thread.start()

    def _start_reader(self):
        sdr = self.sdr

        def run():
            def cb(samples, _ctx):
                if not self._running:
                    try:
                        sdr.cancel_read_async()
                    except Exception:  # noqa: BLE001
                        pass
                    return
                self._last_block = time.monotonic()
                self._push(np.asarray(samples, dtype=np.complex64))
            try:
                sdr.read_samples_async(cb, self.block_size)
            except Exception as e:  # noqa: BLE001
                log.warning("Leitura RTL-SDR terminou: %s", e)
        self._reader = threading.Thread(target=run, daemon=True, name="rtl-read")
        self._reader.start()

    def stop(self):
        """Nunca bloqueia a interface: tudo que pode travar roda em segundo plano."""
        if not self._running:
            return
        self._running = False
        self._ctl.put(None)
        sdr = self.sdr

        def bg():
            try:
                sdr.cancel_read_async()
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=bg, daemon=True).start()

    def close(self):
        self.stop()
        sdr = self.sdr

        def bg():
            reader = self._reader
            if reader is not None:
                reader.join(timeout=3)
            try:
                sdr.close()
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=bg, daemon=True, name="rtl-close").start()

    # ------------------------------------------------------------ controle (fila + tempo limite)
    def _control_loop(self):
        while self._running:
            item = self._ctl.get()
            if item is None:
                return
            name, fn = item
            self._busy_since = time.monotonic()
            try:
                fn(self.sdr)
            except Exception as e:  # noqa: BLE001
                self._on_control_error(name, e)
            finally:
                self._busy_since = 0.0

    def _submit(self, name: str, fn):
        if self._running:
            self._ctl.put((name, fn))
        else:
            try:
                fn(self.sdr)
            except Exception as e:  # noqa: BLE001
                self._on_control_error(name, e)

    def _on_control_error(self, name, e):
        if name == "freq":
            self._say(f"O RTL-SDR não aceitou a frequência: {e}. Mantida a anterior.")
        else:
            log.warning("Ajuste %s falhou: %s", name, e)

    def check_freq(self, hz: float) -> str:
        """'' se o dongle alcança a frequência; senão, explicação para o usuário."""
        lo, hi = tuning_range(self.tuner, library_info().get("blog", False), self.direct_sampling, self.product)
        if lo <= hz <= hi:
            return ""
        what = self.product or f"RTL-SDR ({self.tuner or 'sintonizador desconhecido'})"
        hint = ""
        if hz < 24e6:
            hint = (" Para HF: RTL-SDR Blog V4 (HF pelo conversor interno), V3 com Amostragem direta → Ramo Q, "
                    "ou um upconverter.")
        return f"{what} sintoniza de {lo / 1e6:g} a {hi / 1e6:g} MHz; {hz / 1e6:.4f} MHz está fora.{hint}"

    def set_center_freq(self, hz: float):
        problem = self.check_freq(hz)
        if problem:
            self._say(problem)
            return False
        old = self.center_freq
        self.center_freq = float(hz)

        def do(sdr):
            try:
                sdr.center_freq = int(hz)
            except Exception:
                self.center_freq = old
                raise
        self._submit("freq", do)
        return True

    def set_gain(self, db):
        self.gain = db
        self._submit("gain", lambda sdr: setattr(sdr, "gain", "auto" if db is None else float(db)))

    def set_ppm(self, ppm: int):
        self.ppm = int(ppm)

        def do(sdr):
            try:
                if int(ppm) != 0 or sdr.freq_correction != 0:
                    sdr.freq_correction = int(ppm)
            except Exception:  # noqa: BLE001  (librtlsdr recusa valor igual ao atual)
                pass
        self._submit("ppm", do)

    def set_bias_tee(self, on: bool):
        self.bias_tee = bool(on)
        self._submit("bias", lambda sdr: sdr.set_bias_tee(bool(on)))

    def set_direct_sampling(self, mode: int):
        self.direct_sampling = int(mode)
        self._submit("direct", lambda sdr: sdr.set_direct_sampling(int(mode)))

    # ------------------------------------------------------------ vigia e recuperação
    def _watch_loop(self):
        failures = 0
        while self._running:
            time.sleep(0.25)
            now = time.monotonic()
            if self._busy_since and now - self._busy_since > self.CMD_TIMEOUT_S:
                self._busy_since = 0.0
                self._say("O RTL-SDR não respondeu ao comando; reconectando…")
                stalled = True
            else:
                stalled = now - self._last_block > self.STALL_S
            if not stalled:
                if self.status != "ok" and now - self._last_block < 0.5:
                    self.status = "ok"
                    failures = 0
                    self._say("Recepção restabelecida.")
                continue
            failures += 1
            if failures > self.MAX_RECOVER:
                self.status = "failed"
                self._say("O RTL-SDR parou de responder. Desconecte e reconecte o dongle e clique em Ligar.")
                self._running = False
                return
            self.status = "recovering"
            self._say(f"Sem amostras do RTL-SDR; reconectando (tentativa {failures}/{self.MAX_RECOVER})…")
            self._recover()
            self._last_block = time.monotonic()

    def _recover(self):
        old = self.sdr
        old_reader = self._reader
        threading.Thread(target=lambda: _quiet(old.cancel_read_async), daemon=True).start()
        if old_reader is not None:
            old_reader.join(timeout=2.5)
        if old_reader is not None and old_reader.is_alive():
            log.warning("Leitura antiga não encerrou; abandonando a instância travada")
        else:
            threading.Thread(target=lambda: _quiet(old.close), daemon=True).start()
            time.sleep(0.3)
        try:
            self.sdr = self._open()
        except SourceError as e:
            self._say(str(e).split("\n")[0])
            return
        while not self._ctl.empty():  # comandos pendentes para a instância antiga
            try:
                self._ctl.get_nowait()
            except queue.Empty:
                break
        self._ctl_thread = threading.Thread(target=self._control_loop, daemon=True, name="rtl-ctl")
        self._ctl_thread.start()
        self._start_reader()


def _quiet(fn):
    try:
        fn()
    except Exception:  # noqa: BLE001
        pass
