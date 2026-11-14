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
from contextlib import nullcontext
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


class _DllWithStubs:
    """Embrulha a DLL do driver RTL-SDR Blog para o pyrtlsdr.

    O pyrtlsdr 0.5 liga funções que só existem em algumas compilações (GPIO, dithering, testmode);
    as ausentes viram stubs sem efeito que retornam 0 (sucesso). Retornar erro quebrava a abertura:
    o pyrtlsdr chama rtlsdr_set_dithering logo após abrir o dongle (0.4.1: "Error code -1 when setting
    PLL dithering mode", deixando o dongle preso)."""

    def __init__(self, dll):
        self._dll = dll
        self._stubs = {}
        self._name = getattr(dll, "_name", "rtlsdr.dll")

    def __getattr__(self, name):
        try:
            return getattr(self._dll, name)
        except AttributeError:
            if not name.startswith("rtlsdr_"):
                raise
            if name not in self._stubs:
                def stub(*_a, **_k):
                    return 0
                stub.restype = None
                stub.argtypes = None
                self._stubs[name] = stub
            return self._stubs[name]


_DLL_DIR_HANDLES = []  # os.add_dll_directory: manter a referência (senão o diretório é removido)


_PREF = {"lib": "auto"}          # auto | blog | standard (Configurações → Biblioteca do RTL-SDR)
_CLOSING: list[threading.Thread] = []  # fechamentos em segundo plano ainda em andamento


def set_preference(lib: str):
    _PREF["lib"] = lib if lib in ("auto", "blog", "standard") else "auto"


def _unload():
    for m in [k for k in sys.modules if k == "rtlsdr" or k.startswith("rtlsdr.") or k == "pyrtlsdrlib"]:
        sys.modules.pop(m, None)


def load_library(kind: str | None = None):
    """Carrega a librtlsdr. kind: 'blog' (DLL do driver RTL-SDR Blog incluída no pacote, Windows),
    'standard' (a do pyrtlsdrlib, usada até a 0.3.0) ou None (preferência atual). Retorna o objeto da DLL."""
    if kind is None:
        pref = _PREF["lib"]
        kind = "standard" if pref == "standard" or (pref == "auto" and _LIB_INFO.get("blog_failed")) else "blog"
    blog = _bundled_blog_dir() if sys.platform == "win32" else None
    if kind == "blog" and blog is None:
        kind = "standard"
    if "rtlsdr.librtlsdr" in sys.modules and _LIB_INFO.get("kind") == kind:
        return sys.modules["rtlsdr.librtlsdr"].librtlsdr
    _unload()
    if kind == "blog":
        try:
            import ctypes
            import types
            if not _DLL_DIR_HANDLES:
                _DLL_DIR_HANDLES.append(os.add_dll_directory(str(blog)))
            for dep in ("msvcr100.dll", "libusb-1.0.dll", "pthreadVC2.dll"):
                if (blog / dep).is_file():
                    ctypes.CDLL(str(blog / dep))
            wrapped = _DllWithStubs(ctypes.CDLL(str(blog / "rtlsdr.dll")))
            fake = types.ModuleType("pyrtlsdrlib")
            fake.load_librtlsdr = lambda: wrapped  # o pyrtlsdr usa este carregador primeiro
            sys.modules["pyrtlsdrlib"] = fake
            from rtlsdr.librtlsdr import librtlsdr
            _LIB_INFO.update(name=str(blog / "rtlsdr.dll"), blog=True, kind="blog")
            return librtlsdr
        except Exception as e:  # noqa: BLE001
            log.warning("Driver RTL-SDR Blog não carregou (%s); usando a biblioteca padrão", e)
            _LIB_INFO["error_blog"] = f"{type(e).__name__}: {e}"
            _LIB_INFO["blog_failed"] = True
            _unload()
    from rtlsdr.librtlsdr import librtlsdr
    _LIB_INFO.update(name=getattr(librtlsdr, "_name", "") or "", blog=False, kind="standard")
    return librtlsdr


def _rtlsdr_class(kind: str):
    """Classe RtlSdr usando a biblioteca pedida (recarrega o pyrtlsdr se for preciso trocar)."""
    import importlib
    load_library(kind)
    return importlib.import_module("rtlsdr").RtlSdr


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
    # Shared only for lazy initialization in legacy/lightweight test objects.
    # Normal instances initialize their own lock in __init__.
    _close_init_lock = threading.Lock()
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
        self._close_lock = threading.Lock()
        self._close_requested = False
        self._ctl_thread: threading.Thread | None = None
        self._ctl_stop_sent = False  # one sentinel even after watchdog stops _running
        self._reader_cancel_sent = False  # idempotent cancellation, including watchdog-failed RX
        self._cancel_thread: threading.Thread | None = None  # native cancel must finish before USB close
        self._watch_thread: threading.Thread | None = None
        self._busy_since = 0.0
        self._recovering = threading.Lock()
        self._native_lock = threading.Lock()  # serialize control commands and USB recovery
        self._close_lock = threading.Lock()
        self._close_requested = False
        self.library = ""
        self.sdr = self._open()
        self.tuner = self._tuner_name()
        self.product = self._product_name()
        self.range = tuning_range(self.tuner, library_info().get("blog", False), 0, self.product)

    # ------------------------------------------------------------ abertura
    def _default_factory(self, index: int):
        """Abre o dongle. Automático: driver RTL-SDR Blog e, se ele não abrir (ex.: LIBUSB_ERROR_ACCESS),
        a biblioteca padrão — a mesma que funcionava na 0.3.0."""
        for t in list(_CLOSING):  # um fechamento anterior ainda segura o dongle (WinUSB é exclusivo)
            t.join(timeout=3)
            if not t.is_alive():
                _CLOSING.remove(t)
        pref = _PREF["lib"]
        order = {"blog": ["blog"], "standard": ["standard"]}.get(pref, ["blog", "standard"])
        if _bundled_blog_dir() is None or sys.platform != "win32":
            order = ["standard"]
        errors = []
        for kind in order:
            try:
                cls = _rtlsdr_class(kind)
            except Exception as e:  # noqa: BLE001
                errors.append((kind, e))
                continue
            try:
                dev = self._construct(cls, index)
            except Exception as e:  # noqa: BLE001
                errors.append((kind, e))
                if kind == "blog":
                    _LIB_INFO["blog_failed"] = True
                    _LIB_INFO["error_blog"] = f"{type(e).__name__}: {e}"
                continue
            if errors:
                self._messages.put("RTL-SDR aberto com a biblioteca padrão (a do driver RTL-SDR Blog não abriu: "
                                   f"{errors[0][1]}).")
            self.library = "RTL-SDR Blog" if kind == "blog" else "padrão"
            return dev
        if not errors:
            raise SourceError("Biblioteca librtlsdr indisponível. Reinstale o PT2VHF SDR Tool.")
        detail = "; ".join(f"{'driver RTL-SDR Blog' if k == 'blog' else 'biblioteca padrão'}: {e}" for k, e in errors)
        raise RuntimeError(detail)

    @staticmethod
    def _construct(cls, index):
        """Cria o RtlSdr; se falhar depois de abrir o dongle, fecha o handle antes de seguir
        (senão a próxima tentativa recebe LIBUSB_ERROR_ACCESS, pois o WinUSB é exclusivo)."""
        dev = cls.__new__(cls)
        try:
            cls.__init__(dev, index)
            return dev
        except Exception:
            handle = getattr(dev, "dev_p", None)
            if handle is not None and getattr(handle, "value", None):
                try:
                    sys.modules["rtlsdr.librtlsdr"].librtlsdr.rtlsdr_close(handle)
                except Exception as e:  # noqa: BLE001
                    log.warning("Não foi possível liberar o dongle após a falha: %s", e)
            raise

    def _open(self):
        try:
            sdr = self._factory(self.device_index)
        except SourceError:
            raise
        except Exception as e:  # noqa: BLE001
            msg = f"Não foi possível abrir o RTL-SDR #{self.device_index}: {e}\n\n"
            if "ACCESS" in str(e).upper():
                msg += ("Acesso negado ao dongle: outro programa (SDR#, SDR++, Sat Tool…) ou outra cópia do "
                        "PT2VHF SDR Tool pode estar usando o RTL-SDR, ou o driver da interface 0 não é WinUSB.\n"
                        "Feche os outros programas, desconecte e reconecte o dongle. Se continuar, use "
                        "Ajuda → Preparar RTL-SDR e, em Configurações, teste a opção Biblioteca do RTL-SDR → Padrão.")
            else:
                msg += ("Se for a primeira vez, use Ajuda → Preparar RTL-SDR (instala o driver WinUSB) "
                        "ou o Zadig, e reconecte o dongle.")
            raise SourceError(msg) from e
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
        self._ctl_stop_sent = False
        self._reader_cancel_sent = False
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
        self._reader_cancel_sent = False
        self._reader = threading.Thread(target=run, daemon=True, name="rtl-read")
        self._reader.start()

    def stop(self):
        """Nunca bloqueia a interface: tudo que pode travar roda em segundo plano.

        A vigia pode ter marcado _running=False após MAX_RECOVER enquanto a
        thread de controle ainda espera em Queue.get(). Nesse caso também é
        obrigatório enviar a sentinela; caso contrário a thread daemon vaza
        até o shutdown do Python, mesmo depois de close().
        """
        was_running = self._running
        self._running = False
        ctl = self._ctl_thread
        if ctl is not None and ctl.is_alive() and not self._ctl_stop_sent:
            self._ctl_stop_sent = True
            self._ctl.put(None)
        # The watchdog can set _running=False while the native async reader
        # is still blocked.  A later close() must cancel that read before its
        # bounded join and sdr.close(), even when stop() is called post-failure.
        reader = self._reader
        should_cancel = was_running or (reader is not None and reader.is_alive())
        if should_cancel and not getattr(self, "_reader_cancel_sent", False):
            self._reader_cancel_sent = True
            sdr = self.sdr

            def bg():
                try:
                    sdr.cancel_read_async()
                except Exception:  # noqa: BLE001
                    pass
            cancel_thread = threading.Thread(target=bg, daemon=True, name="rtl-cancel")
            # Register before starting so close() can await native cancellation.
            self._cancel_thread = cancel_thread
            cancel_thread.start()

    def close(self):
        # UI/engine teardown may call close more than once (or concurrently).
        # Calling librtlsdr.close twice on the same native handle is unsafe.
        lock = getattr(self, "_close_lock", None)
        if lock is None:  # permits lightweight object.__new__ test doubles
            # Atomic publication: two concurrent close() callers must not
            # create distinct locks and both release the same native handle.
            with RtlSdrSource._close_init_lock:
                lock = getattr(self, "_close_lock", None)
                if lock is None:
                    lock = threading.Lock()
                    self._close_lock = lock
        with lock:
            if getattr(self, "_close_requested", False):
                return
            self._close_requested = True
        self.stop()
        def bg():
            # The watchdog may replace both the reader and SDR during recovery.
            # Wait for it before snapshotting either object.
            # Nenhuma thread de controle deve sobreviver ao encerramento do SDR.
            # A sentinela já foi enviada em stop(); aguarda em background para não
            # bloquear a GUI quando a biblioteca USB estiver lenta/travada.
            ctl = self._ctl_thread
            if ctl is not None and ctl is not threading.current_thread():
                ctl.join(timeout=getattr(self, "CTL_CLOSE_JOIN_S", 3.0))
                if ctl.is_alive():
                    # A queued native tuner command may still be executing.
                    # Never free its USB handle until the control thread exits.
                    log.warning("RTL-SDR control thread still active; deferring native close")
                    ctl.join()
            watcher = self._watch_thread
            if watcher is not None and watcher is not threading.current_thread():
                watcher.join(timeout=getattr(self, "WATCH_CLOSE_JOIN_S", 1.0))
                if watcher.is_alive():
                    # The watchdog can be inside _recover(), touching USB.
                    log.warning("RTL-SDR watchdog still active; deferring native close")
                    watcher.join()
            reader = self._reader
            if reader is not None and reader is not threading.current_thread():
                reader.join(timeout=getattr(self, "READER_CLOSE_JOIN_S", 3.0))
                if reader.is_alive():
                    log.warning("RTL-SDR reader still active; deferring native close until it exits")
                    reader.join()
            # A cancel_read_async worker can outlive the async reader. Never
            # release its native handle while that worker is still in librtlsdr.
            cancel_thread = getattr(self, "_cancel_thread", None)
            if cancel_thread is not None and cancel_thread is not threading.current_thread():
                cancel_thread.join(timeout=getattr(self, "CANCEL_CLOSE_JOIN_S", 3.0))
                if cancel_thread.is_alive():
                    log.warning("RTL-SDR cancellation still active; deferring native close")
                    cancel_thread.join()
            sdr = self.sdr  # capture after watchdog recovery has finished
            if sdr is not None:
                try:
                    sdr.close()
                except Exception:  # noqa: BLE001
                    pass
        t = threading.Thread(target=bg, daemon=True, name="rtl-close")
        _CLOSING.append(t)
        t.start()

    # ------------------------------------------------------------ controle (fila + tempo limite)
    def _control_loop(self):
        while self._running:
            item = self._ctl.get()
            if item is None:
                return
            name, fn = item
            self._busy_since = time.monotonic()
            try:
                with getattr(self, "_native_lock", nullcontext()):
                    if not self._running or getattr(self, "_close_requested", False):
                        return
                    fn(self.sdr)
            except Exception as e:  # noqa: BLE001
                self._on_control_error(name, e)
            finally:
                self._busy_since = 0.0

    def _submit(self, name: str, fn):
        # A late UI/engine setter must not touch a USB handle once close()
        # has been requested.  Pre-start configuration remains supported.
        if getattr(self, "_close_requested", False):
            log.debug("Ignoring RTL-SDR %s after close requested", name)
            return
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
        """Do not reopen a native USB handle while its old users are active.

        A stuck native driver fails closed; this runs in the watchdog thread,
        never in Qt. Synthetic tests cannot establish real-device stability.
        """
        with getattr(self, "_native_lock", nullcontext()):
            if not self._running or getattr(self, "_close_requested", False):
                return
            old = self.sdr
            old_reader = self._reader
            cancel_thread = getattr(self, "_cancel_thread", None)
            if cancel_thread is None or not cancel_thread.is_alive():
                cancel_thread = threading.Thread(
                    target=lambda: _quiet(old.cancel_read_async),
                    daemon=True, name="rtl-recover-cancel",
                )
                self._reader_cancel_sent = True
                self._cancel_thread = cancel_thread
                cancel_thread.start()
            cancel_thread.join(timeout=getattr(self, "RECOVER_CANCEL_JOIN_S", 2.5))
            if cancel_thread.is_alive():
                self.status = "failed"
                self._running = False
                self._say("RTL-SDR: cancelamento USB travado; reconexão suspensa para proteger o dispositivo.")
                return
            if old_reader is not None and old_reader is not threading.current_thread():
                old_reader.join(timeout=getattr(self, "RECOVER_READER_JOIN_S", 2.5))
                if old_reader.is_alive():
                    self.status = "failed"
                    self._running = False
                    self._say("RTL-SDR: leitura USB não encerrou; reconexão suspensa para evitar corrupção de memória.")
                    return
            if not self._running or getattr(self, "_close_requested", False):
                return
            try:
                old.close()
            except Exception as exc:  # noqa: BLE001
                self.status = "failed"
                self._running = False
                self._say(f"RTL-SDR: falha ao liberar dispositivo; reconexão suspensa ({exc}).")
                return
            self.sdr = None  # the old native handle must not be closed twice
            if not self._running or getattr(self, "_close_requested", False):
                return
            try:
                new_sdr = self._open()
            except SourceError as exc:
                self.status = "failed"
                self._running = False
                self._say(str(exc).split("\\n")[0])
                return
            except Exception as exc:  # noqa: BLE001
                self.status = "failed"
                self._running = False
                self._say(f"RTL-SDR: reabertura falhou ({exc}).")
                return
            self.sdr = new_sdr
            while not self._ctl.empty():
                try:
                    self._ctl.get_nowait()
                except queue.Empty:
                    break
            if self._running and not getattr(self, "_close_requested", False):
                self._start_reader()


def _quiet(fn):
    try:
        fn()
    except Exception:  # noqa: BLE001
        pass
