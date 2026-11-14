"""P0: native RTL async cancellation must not race from callback and stop.

Deterministic fake-device regression. It does not prove the cause of the
v0.13.3 Windows field crash or validate real USB driver behavior.
"""
from __future__ import annotations

import queue
import threading

from pt2vhf.sources.rtlsdr_source import RtlSdrSource


def _source_with_callback_device():
    reader_ready = threading.Event()
    fire_callback = threading.Event()
    cancelled = threading.Event()
    calls = []
    calls_lock = threading.Lock()

    class FakeSdr:
        def read_samples_async(self, callback, _block_size):
            reader_ready.set()
            if not fire_callback.wait(3):
                raise AssertionError("test did not release the callback")
            callback([], None)

        def cancel_read_async(self):
            with calls_lock:
                calls.append(threading.current_thread().name)
            cancelled.set()

    src = object.__new__(RtlSdrSource)
    src.sdr = FakeSdr()
    src._running = True
    src._close_requested = False
    src._ctl = queue.Queue()
    src._ctl_thread = None
    src._ctl_stop_sent = False
    src._watch_thread = None
    src._reader_cancel_sent = False
    src._cancel_thread = None
    src._cancel_state_lock = threading.Lock()
    src._native_closing = False
    src.block_size = 16
    return src, reader_ready, fire_callback, cancelled, calls


def test_callback_and_stop_do_not_double_cancel_native_usb():
    src, ready, fire, cancelled, calls = _source_with_callback_device()
    src._start_reader()
    try:
        assert ready.wait(2)
        src.stop()
        assert cancelled.wait(2), "stop did not request native cancellation"
        fire.set()  # callback sees _running=False after stop's cancellation
        src._reader.join(timeout=2)
        assert not src._reader.is_alive()
        assert calls == ["rtl-cancel"], "callback issued a second native cancellation"
    finally:
        fire.set()
        src._reader.join(timeout=2)
        worker = src._cancel_thread
        if worker is not None:
            worker.join(timeout=2)


def test_watchdog_stopped_callback_requests_cancel_off_reader_thread():
    src, ready, fire, cancelled, calls = _source_with_callback_device()
    src._start_reader()
    try:
        assert ready.wait(2)
        src._running = False  # watchdog failed before stop() was called
        fire.set()
        assert cancelled.wait(2), "callback did not schedule cancellation"
        src._reader.join(timeout=2)
        assert not src._reader.is_alive()
        assert calls == ["rtl-cancel"], "native cancellation ran on the reader callback"
    finally:
        fire.set()
        src._reader.join(timeout=2)
        worker = src._cancel_thread
        if worker is not None:
            worker.join(timeout=2)
