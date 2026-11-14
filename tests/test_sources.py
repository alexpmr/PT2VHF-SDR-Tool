import socket
import struct
import threading
import wave

import numpy as np

from pt2vhf.sources.network_sources import RtlTcpSource
from pt2vhf.sources.sim_sources import WavIQSource


def test_rtl_tcp_client_protocol():
    # rtl_tcp is a byte stream: recv() is not guaranteed to return one command
    # per call. The fake server must also drain commands before the client
    # closes, rather than sending 1 MB first and racing Windows socket teardown.
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cmds = []
    commands_ready = threading.Event()
    expected = {
        (0x02, 240_000), (0x01, 145_500_000), (0x05, 0),
        (0x03, 1), (0x04, 200), (0x01, 146_000_000),
    }

    def serve():
        try:
            c, _ = srv.accept()
            with c:
                c.settimeout(5)
                c.sendall(b"RTL0" + struct.pack(">II", 5, 29))
                # One complete IQ block is sufficient; a large sendall()
                # can block command reads until the client is already closed.
                c.sendall(bytes([200]) * (2 * 16384))
                pending = bytearray()
                while not expected.issubset(set(cmds)):
                    chunk = c.recv(4096)
                    if not chunk:
                        break
                    pending.extend(chunk)
                    while len(pending) >= 5:
                        cmds.append(struct.unpack(">BI", pending[:5]))
                        del pending[:5]
                if expected.issubset(set(cmds)):
                    commands_ready.set()
        finally:
            srv.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    src = RtlTcpSource(240_000, 145.5e6, "127.0.0.1", port, gain=20.0)
    try:
        assert src.tuner == "R820T"
        src.start()
        blk = src.read(timeout=3)
        src.set_center_freq(146e6)
        assert blk is not None and len(blk) == src.block_size
        assert np.allclose(blk[:10], (200 - 127.4) / 128 * (1 + 1j), atol=1e-3)
        assert commands_ready.wait(5), f"rtl_tcp commands incomplete: {cmds!r}"
    finally:
        src.close()
        t.join(timeout=5)
    assert not t.is_alive()
    assert expected.issubset(set(cmds))


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
