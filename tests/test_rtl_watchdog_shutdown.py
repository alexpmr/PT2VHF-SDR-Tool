"""P0: RTL control-thread teardown when the watchdog has already stopped RX.

This uses a fake SDR; it does not exercise native USB/DLL or prove the field
crash cause. It guards against leaving a daemon thread in Queue.get() when
MAX_RECOVER marks _running=False before MainWindow/Engine calls close().
"""
from __future__ import annotations

import queue
import threading

from pt2vhf.sources.rtlsdr_source import RtlSdrSource


def test_rtl_control_thread_exits_if_watchdog_stopped_receiver():
    entered_get = threading.Event()
    closed = threading.Event()

    class NotifyingQueue(queue.Queue):
        def get(self, *args, **kwargs):
            entered_get.set()
            return super().get(*args, **kwargs)

    class FakeSdr:
        def close(self):
            closed.set()

    src = object.__new__(RtlSdrSource)
    src._running = True
    src._ctl = NotifyingQueue()
    src._ctl_stop_sent = False
    src._ctl_thread = threading.Thread(
        target=src._control_loop, daemon=True, name="test-rtl-ctl"
    )
    src._reader = None
    src._watch_thread = None
    src.sdr = FakeSdr()
    src._ctl_thread.start()

    try:
        assert entered_get.wait(2), "control thread did not enter Queue.get"
        # Simulate _watch_loop's MAX_RECOVER exit, which sets this flag to
        # False without sending a control-queue sentinel.
        src._running = False
        src.close()
        src._ctl_thread.join(timeout=2)
        assert not src._ctl_thread.is_alive(), (
            "control thread leaked after watchdog shutdown"
        )
        assert closed.wait(2), "background SDR close did not complete"
        # Repeated stop must not enqueue a second sentinel.
        src.stop()
        assert src._ctl.empty()
    finally:
        # Never strand a test daemon if an assertion fails.
        src._running = False
        src._ctl.put(None)
        src._ctl_thread.join(timeout=2)


def test_rtl_stop_before_start_does_not_poison_control_queue():
    src = object.__new__(RtlSdrSource)
    src._running = False
    src._ctl = queue.Queue()
    src._ctl_thread = None
    src._ctl_stop_sent = False
    src._reader = None  # Mirrors __init__: stop() must see an initialized reader slot.
    src._reader_cancel_sent = False
    src.stop()
    assert src._ctl.empty()


def test_watchdog_failure_cancels_native_async_read_before_close():
    """A watchdog-stopped source must still cancel an outstanding native read.

    This fake models a blocking async USB read. It is NOT a real RTL-SDR test.
    """
    read_started = threading.Event()
    read_cancelled = threading.Event()
    read_exited = threading.Event()
    closed = threading.Event()
    order = []

    class FakeSdr:
        def cancel_read_async(self):
            order.append("cancel")
            read_cancelled.set()

        def close(self):
            order.append("close")
            closed.set()

    def blocking_read():
        read_started.set()
        try:
            read_cancelled.wait(2)
        finally:
            read_exited.set()

    src = object.__new__(RtlSdrSource)
    src._running = False  # watchdog MAX_RECOVER already ran
    src._ctl = queue.Queue()
    src._ctl_thread = None
    src._ctl_stop_sent = False
    src._reader_cancel_sent = False
    src._watch_thread = None
    src.sdr = FakeSdr()
    src._reader = threading.Thread(target=blocking_read, daemon=True)
    src._reader.start()
    try:
        assert read_started.wait(2)
        src.close()
        assert read_cancelled.wait(2), "stalled reader was never cancelled"
        assert read_exited.wait(2), "reader did not exit after cancellation"
        assert closed.wait(2), "SDR close did not complete"
        assert order == ["cancel", "close"]
        src.stop()
        assert order == ["cancel", "close"], "stop must be idempotent"
    finally:
        read_cancelled.set()
        src._reader.join(timeout=2)

def test_native_close_waits_for_stuck_reader_even_after_join_timeout():
    """A native USB handle must not close while async read is still alive.

    Synthetic thread only: this does not validate a physical RTL-SDR driver.
    """
    import time

    reader_started = threading.Event()
    release_reader = threading.Event()
    native_closed = threading.Event()

    class FakeSdr:
        def close(self):
            native_closed.set()

    def blocked_read():
        reader_started.set()
        release_reader.wait(5)

    src = object.__new__(RtlSdrSource)
    src._running = False  # watchdog has already stopped RX
    src._ctl = queue.Queue()
    src._ctl_thread = None
    src._ctl_stop_sent = False
    src._reader_cancel_sent = True  # cancellation was already requested
    src._watch_thread = None
    src.READER_CLOSE_JOIN_S = 0.05  # exercise timeout without a 3s test delay
    src.sdr = FakeSdr()
    src._reader = threading.Thread(target=blocked_read, daemon=True)
    src._reader.start()
    try:
        assert reader_started.wait(2)
        src.close()
        time.sleep(0.15)  # longer than the first bounded reader join
        assert not native_closed.is_set(), "native close raced an active async read"
        release_reader.set()
        src._reader.join(timeout=2)
        assert native_closed.wait(2), "native close never followed reader exit"
    finally:
        release_reader.set()
        src._reader.join(timeout=2)

def test_native_close_is_idempotent_with_concurrent_teardown():
    """A repeated Qt/engine shutdown must never close one USB handle twice.

    Uses a fake SDR only; real librtlsdr behavior still requires bench testing.
    """
    close_calls = []
    native_closed = threading.Event()
    calls_lock = threading.Lock()

    class FakeSdr:
        def close(self):
            with calls_lock:
                close_calls.append(1)
            native_closed.set()

    src = object.__new__(RtlSdrSource)
    src._running = False
    src._ctl = queue.Queue()
    src._ctl_thread = None
    src._ctl_stop_sent = False
    src._reader = None
    src._reader_cancel_sent = False
    src._watch_thread = None
    src._close_lock = threading.Lock()
    src._close_requested = False
    src.sdr = FakeSdr()

    gate = threading.Barrier(9)

    def request_close():
        gate.wait(timeout=5)
        src.close()

    callers = [threading.Thread(target=request_close) for _ in range(8)]
    for caller in callers:
        caller.start()
    gate.wait(timeout=5)
    for caller in callers:
        caller.join(timeout=5)
        assert not caller.is_alive(), "close() blocked a caller"
    assert native_closed.wait(5), "native close did not run"
    assert close_calls == [1], "native handle was closed more than once"
    src.close()
    assert close_calls == [1], "later close() retried native close"


def test_native_close_waits_for_active_control_and_watchdog_threads():
    """Do not free a USB handle while a native tuner command or recovery is active.

    Synthetic synchronization only: real USB-driver behavior needs bench QA.
    """
    for role in ("control", "watchdog"):
        entered = threading.Event()
        release = threading.Event()
        native_closed = threading.Event()

        class FakeSdr:
            def close(self):
                native_closed.set()

        src = object.__new__(RtlSdrSource)
        src._running = True
        src._ctl = queue.Queue()
        src._ctl_stop_sent = False
        src._reader_cancel_sent = False
        src._reader = None
        src._ctl_thread = None
        src._watch_thread = None
        src.CTL_CLOSE_JOIN_S = 0.05
        src.WATCH_CLOSE_JOIN_S = 0.05
        src.sdr = FakeSdr()

        if role == "control":
            def blocking_command(_sdr):
                entered.set()
                release.wait(5)
            src._ctl.put(("gain", blocking_command))
            active = threading.Thread(target=src._control_loop, daemon=True)
            src._ctl_thread = active
        else:
            def blocking_recovery():
                entered.set()
                release.wait(5)
            active = threading.Thread(target=blocking_recovery, daemon=True)
            src._watch_thread = active

        active.start()
        try:
            assert entered.wait(2), f"{role} did not start"
            src.close()
            assert not native_closed.wait(0.15), (
                f"native close raced an active {role} thread"
            )
            release.set()
            active.join(timeout=2)
            assert not active.is_alive(), f"{role} did not finish"
            assert native_closed.wait(2), (
                f"native close did not follow {role} completion"
            )
        finally:
            release.set()
            active.join(timeout=2)
