import socket
import struct
import threading
import wave

import numpy as np

from pt2vhf.sources.network_sources import RtlTcpSource
from pt2vhf.sources.sim_sources import WavIQSource


def test_rtl_tcp_client_protocol():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cmds = []

    def serve():
        c, _ = srv.accept()
        c.sendall(b"RTL0" + struct.pack(">II", 5, 29))
        c.settimeout(0.2)
        data = np.full(1_000_000, 200, np.uint8).tobytes()
        try:
            c.sendall(data)
            while True:
                b = c.recv(5)
                if not b:
                    break
                cmds.append(struct.unpack(">BI", b))
        except OSError:
            pass
        c.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    src = RtlTcpSource(240_000, 145.5e6, "127.0.0.1", port, gain=20.0)
    assert src.tuner == "R820T"
    src.start()
    blk = src.read(timeout=3)
    src.set_center_freq(146e6)
    src.close()
    assert blk is not None and len(blk) == src.block_size
    assert np.allclose(blk[:10], (200 - 127.4) / 128 * (1 + 1j), atol=1e-3)
    t.join(timeout=2)
    assert (0x02, 240_000) in cmds and (0x01, 145_500_000) in cmds and (0x04, 200) in cmds
    assert (0x01, 146_000_000) in cmds


def test_wav_iq_source(tmp_path):
    p = tmp_path / "SDRSharp_20260101_120000Z_145570000Hz_IQ.wav"
    n = 48_000
    x = (0.5 * np.exp(2j * np.pi * 1000 * np.arange(n) / 240_000))
    inter = np.empty(2 * n, np.int16)
    inter[0::2] = (x.real * 32767).astype(np.int16)
    inter[1::2] = (x.imag * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(240_000)
        w.writeframes(inter.tobytes())
    src = WavIQSource(str(p))
    assert src.center_freq == 145_570_000 and src.sample_rate == 240_000
    blk = src._read_block()
    assert np.allclose(blk[:100], x[:100], atol=1e-3)
    src.close()


def test_engine_with_fixed_center_file(tmp_path):
    from pt2vhf.dsp.receiver import Receiver
    from pt2vhf.engine import Engine
    p = tmp_path / "rec_100000000Hz.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(240_000)
        w.writeframes(np.zeros(2 * 24000, np.int16).tobytes())
    src = WavIQSource(str(p))
    e = Engine(None)
    e.source, e.rx = src, Receiver(240_000)
    e.tune(100.05e6)
    assert src.center_freq == 100e6 and e.rx.offset_hz == 50_000
    e.tune(200e6)
    assert src.center_freq == 100e6 and abs(e.rx.offset_hz) <= 120_000
    src.close()
