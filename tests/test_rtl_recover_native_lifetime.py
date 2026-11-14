"""P0: deterministic USB recovery lifetime ordering (fake devices only).

These tests prevent known use-after-free patterns but do not prove the cause
of the v0.13.3 field crash or stability with a physical RTL-SDR.
"""
import queue
import threading

from pt2vhf.sources.rtlsdr_source import RtlSdrSource


def source_with_fake(old, new):
    src = object.__new__(RtlSdrSource)
    src.sdr = old
    src._running = True
    src._close_requested = False
    src._native_lock = threading.Lock()
    src._reader = None
    src._cancel_thread = None
    src._reader_cancel_sent = False
    src._ctl = queue.Queue()
    src.status = "ok"
    messages = []
    reopened = threading.Event()
    restarted = threading.Event()
    src._say = messages.append

    def reopen():
        reopened.set()
        return new

    src._open = reopen
    src._start_reader = restarted.set
    return src, messages, reopened, restarted


def test_recovery_fails_closed_if_native_cancel_is_stuck():
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()

    class Old:
        def cancel_read_async(self):
            entered.set()
            release.wait(5)

        def close(self):
            closed.set()

    src, messages, reopened, _ = source_with_fake(Old(), object())
    src.RECOVER_CANCEL_JOIN_S = 0.05
    try:
        src._recover()
        assert entered.is_set()
        assert src.status == "failed"
        assert not src._running
        assert not closed.is_set(), "old USB handle closed during native cancel"
        assert not reopened.is_set(), "new handle opened while cancel was active"
        assert any("cancelamento" in msg for msg in messages)
    finally:
        release.set()
        src._cancel_thread.join(timeout=2)


def test_recovery_waits_for_native_close_before_reopening():
    closing = threading.Event()
    release = threading.Event()
    old_closed = threading.Event()
    new = object()

    class Old:
        def cancel_read_async(self):
            pass

        def close(self):
            closing.set()
            release.wait(5)
            old_closed.set()

    src, _, reopened, restarted = source_with_fake(Old(), new)
    worker = threading.Thread(target=src._recover, daemon=True)
    worker.start()
    try:
        assert closing.wait(2)
        assert not reopened.wait(0.15), "reopen raced an in-flight native close"
        release.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert old_closed.is_set()
        assert reopened.is_set()
        assert restarted.is_set()
        assert src.sdr is new
    finally:
        release.set()
        worker.join(timeout=2)


def test_recovery_does_not_reopen_after_concurrent_stop():
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()

    class Old:
        def cancel_read_async(self):
            entered.set()
            release.wait(5)

        def close(self):
            closed.set()

    src, _, reopened, restarted = source_with_fake(Old(), object())
    worker = threading.Thread(target=src._recover, daemon=True)
    worker.start()
    try:
        assert entered.wait(2)
        src._running = False  # stop() while watchdog is cancelling USB
        release.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert not closed.is_set()
        assert not reopened.is_set()
        assert not restarted.is_set()
    finally:
        release.set()
        worker.join(timeout=2)


def test_recovery_waits_for_inflight_control_command():
    command_entered = threading.Event()
    release_command = threading.Event()
    cancel_entered = threading.Event()

    class Old:
        def cancel_read_async(self):
            cancel_entered.set()

        def close(self):
            pass

    src, _, reopened, _ = source_with_fake(Old(), object())
    src._busy_since = 0.0

    def command(_sdr):
        command_entered.set()
        release_command.wait(5)

    src._ctl.put(("gain", command))
    control = threading.Thread(target=src._control_loop, daemon=True)
    control.start()
    recovery = None
    try:
        assert command_entered.wait(2)
        recovery = threading.Thread(target=src._recover, daemon=True)
        recovery.start()
        assert not cancel_entered.wait(0.15), "recovery overlapped native control"
        release_command.set()
        assert cancel_entered.wait(2)
        recovery.join(timeout=2)
        assert not recovery.is_alive()
        assert reopened.is_set()
    finally:
        release_command.set()
        src._running = False
        src._ctl.put(None)
        control.join(timeout=2)
        if recovery is not None:
            recovery.join(timeout=2)
