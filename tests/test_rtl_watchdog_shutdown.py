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
    src.stop()
    assert src._ctl.empty()
