"""Fonte RTL-SDR: nada trava a interface, recuperação automática e faixas sem suporte (dongle simulado)."""
import threading
import time

import numpy as np

from pt2vhf.sources.rtlsdr_source import RtlSdrSource, tuning_range


class FakeRtl:
    opened = 0

    def __init__(self, idx, bad_freqs=(), close_hang=0.0):
        FakeRtl.opened += 1
        self.sample_rate = 0
        self._f = 0
        self.gain = "auto"
        self.freq_correction = 0
        self.bad = bad_freqs
        self.close_hang = close_hang
        self.stall = False
        self._cancel = threading.Event()

    @property
    def center_freq(self):
        return self._f

    @center_freq.setter
    def center_freq(self, v):
        if any(lo <= v <= hi for lo, hi in self.bad):
            raise IOError("Error code -1 when setting center freq")
        self._f = v

    def get_gains(self):
        return [0, 100, 200]

    def get_tuner_type(self):
        return 5

    def set_bias_tee(self, on):
        pass

    def set_direct_sampling(self, m):
        pass

    def read_samples_async(self, cb, n):
        while not self._cancel.is_set():
            if not self.stall:
                cb(np.zeros(n, np.complex64), None)
            time.sleep(0.02)

    def cancel_read_async(self):
        self._cancel.set()

    def close(self):
        time.sleep(self.close_hang)


def _src(**kw):
    devs = []

    def factory(i):
        d = FakeRtl(i, **kw)
        devs.append(d)
        return d
    s = RtlSdrSource(1_200_000, 145.5e6, sdr_factory=factory)
    s.STALL_S = 0.5
    return s, devs


def test_stall_is_detected_and_recovered():
    s, devs = _src()
    s.start()
    assert s.read(timeout=1) is not None
    devs[-1].stall = True  # USB parou de entregar amostras, sem erro
    t0 = time.time()
    while len(devs) < 2 and time.time() - t0 < 5:
        time.sleep(0.05)
    assert len(devs) == 2 and devs[-1].center_freq == int(145.5e6)
    while not s._q.empty():
        s._q.get_nowait()
    assert s.read(timeout=2) is not None  # voltou a receber sem o usuário fazer nada
    msgs = " ".join(s.pop_messages())
    assert "reconectando" in msgs
    s.close()


def test_out_of_range_and_rejected_frequency():
    s, devs = _src(bad_freqs=[(400e6, 401e6)])
    s.start()
    assert s.set_center_freq(7.1e6) is False  # HF num RTL-SDR comum: recusa com aviso
    assert s.center_freq == 145.5e6 and "fora" in " ".join(s.pop_messages())
    s.set_center_freq(400.5e6)                 # o dongle recusa: volta para a anterior
    time.sleep(0.3)
    assert s.center_freq == 145.5e6 and "não aceitou" in " ".join(s.pop_messages())
    s.set_center_freq(146e6)
    time.sleep(0.2)
    assert devs[-1].center_freq == int(146e6)
    s.close()


def test_close_never_blocks_the_caller():
    s, _ = _src(close_hang=10.0)
    s.start()
    t0 = time.time()
    s.close()
    assert time.time() - t0 < 0.5


def test_tuning_range_v4():
    assert tuning_range("R828D", True, 0, "RTLSDRBlog Blog V4")[0] < 1e6
    assert tuning_range("R828D", False, 0, "RTLSDRBlog Blog V4")[0] == 24e6
    assert tuning_range("R820T", True, 0, "")[0] == 24e6
    assert tuning_range("R820T", False, 2, "")[1] == 28.8e6
