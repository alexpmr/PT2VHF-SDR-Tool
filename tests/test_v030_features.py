import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib

import numpy as np

from pt2vhf import updater
from pt2vhf.dsp.receiver import Receiver
from pt2vhf.engine import Engine
from pt2vhf.sources.sim_sources import SimulatorSource
from pt2vhf.timeshift import TimeShiftBuffer
from pt2vhf.transcribe import Transcriber, find_callsigns


def test_timeshift_buffer_roundtrip_and_wrap():
    ts = TimeShiftBuffer(1000, 2.0)  # 2000 amostras
    x = (np.linspace(-0.9, 0.9, 1500) * (1 + 1j)).astype(np.complex64)
    ts.append(x[:1000], 100e6)
    ts.append(x[1000:], 101e6)
    got, c = ts.read(200, 100)
    assert np.allclose(got, x[200:300], atol=1 / 127) and c == 100e6
    assert ts.read(1200, 10)[1] == 101e6
    y = (0.5 * np.ones(1500)).astype(np.complex64)
    ts.append(y, 101e6)  # total 3000 > capacidade: as 1000 mais antigas somem
    assert ts.oldest() == 1000 and ts.available_seconds == 2.0
    got, c = ts.read(0, 50)  # pedido antigo é ajustado para o mais antigo disponível
    assert np.allclose(got, x[1000:1050], atol=1 / 127)


def _engine():
    src = SimulatorSource(1_200_000, 145.5e6, realtime=False)
    e = Engine(None)
    e.source, e.rx = src, Receiver(src.sample_rate)
    e.timeshift = TimeShiftBuffer(src.sample_rate, 10)
    e.tune(145.430e6)
    return e, src


def test_replay_past_audio():
    e, src = _engine()
    dur = src.block_size / src.sample_rate
    for _ in range(int(5 / dur)):
        e.process_block(src.generate(src.block_size))
    # a 'voz' do simulador está desligada entre 7 s e 10 s; reouvimos o trecho de antes
    e.start_replay(4.0)
    e.process_block(src.generate(src.block_size))
    assert e.replay_pos is not None and 3.5 < e.replay_seconds_behind() < 4.5
    for _ in range(int(2 / dur)):
        e.process_block(src.generate(src.block_size))
    assert e.replay_pos is not None
    e.stop_replay()
    e.process_block(src.generate(src.block_size))
    assert e.replay_pos is None and abs(e.rx.offset_hz - (e.vfo - src.center_freq)) < 1


def test_extra_receivers_mix_audio():
    e, src = _engine()
    e.rx.muted = True                       # principal mudo: só os extras soam
    ex = e.add_extra(145.650e6, "AM", 6000)  # tom de 1 kHz do simulador
    out = []
    e.audio_tap = lambda a, r: out.append(a)
    for _ in range(30):
        e.process_block(src.generate(src.block_size))
    a = np.concatenate(out[10:])
    spec = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    assert abs(np.argmax(spec) * 48000 / len(a) - 1000) < 20 and ex.in_span
    e.remove_extra(ex)
    e.process_block(src.generate(src.block_size))
    assert not e.extras


def test_capture_if_for_assistant():
    e, src = _engine()
    got = []
    done = threading.Event()
    e.capture_if(0.5, lambda iq, fs: (got.append((iq, fs)), done.set()))
    for _ in range(20):
        e.process_block(src.generate(src.block_size))
    assert done.wait(5)
    iq, fs = got[0]
    assert fs == 240_000 and len(iq) >= 120_000 and not e.rx.keep_if


def test_callsigns_and_transcriber_queue():
    assert find_callsigns("cq cq aqui py2abc chamando pt2vhf, câmbio k1abc") == ["PY2ABC", "PT2VHF", "K1ABC"]

    class FakeSeg:
        text = " PY2XYZ na escuta "

    class FakeModel:
        def transcribe(self, path, language, vad_filter):
            return [FakeSeg()], None

    res, ev = [], threading.Event()
    t = Transcriber(lambda p, txt, calls: (res.append((p, txt, calls)), ev.set()), model=FakeModel())
    t.submit("x.wav")
    assert ev.wait(3)
    t.stop()
    assert res[0] == ("x.wav", "PY2XYZ na escuta", ["PY2XYZ"])


def test_updater_check_download_and_integrity(tmp_path, monkeypatch):
    payload = b"MZ" + bytes(range(256)) * 400
    sha = hashlib.sha256(payload).hexdigest()
    state = {"sha": sha}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/update.php"):
                assert "product=sdr" in self.path and "kind=installer" in self.path
                assert self.headers["User-Agent"].startswith("PT2VHF-SDR-Tool/")
                body = json.dumps({"schema": 1, "product": "sdr", "status": "available", "version": "9.9.9",
                                   "date": "2026-11-07", "notes": "teste", "page": "https://www.pt2vhf.com/sdr",
                                   "files": [{"kind": "installer", "name": "PT2VHF-SDR-Tool-9.9.9-win-x64-setup.exe",
                                              "url": f"http://127.0.0.1:{port}/f.exe", "size": len(payload),
                                              "sha256": state["sha"]}]}).encode()
            else:
                body = payload
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/update.php"
    # URL fora de www.pt2vhf.com é recusada (somente o site oficial)
    info = updater.check("installer", base_url=base)
    assert info is not None and info.version == "9.9.9" and info.file is None
    info = updater.check("installer", base_url=base, allow_test_host=True)
    p = updater.download(info, dest_dir=str(tmp_path))
    assert p.read_bytes() == payload
    state["sha"] = "0" * 64
    info = updater.check("installer", base_url=base, allow_test_host=True)
    try:
        updater.download(info, dest_dir=str(tmp_path))
        raise AssertionError("deveria falhar")
    except updater.UpdateError:
        pass
    assert not (tmp_path / "PT2VHF-SDR-Tool-9.9.9-win-x64-setup.exe").exists() or \
        (tmp_path / "PT2VHF-SDR-Tool-9.9.9-win-x64-setup.exe").read_bytes() == payload
    srv.shutdown()
    assert updater.is_newer("0.10.0", "0.9.9") and not updater.is_newer("0.2.0", "0.3.0")
