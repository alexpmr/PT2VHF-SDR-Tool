import json
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

from pt2vhf.webserver import WebServer, detect_lan_ipv4


def _get(url, headers=None, n=None, timeout=5):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, (r.read(n) if n else r.read()), r.headers


def _server(lan=False, port=0):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    spec = np.linspace(-100, -40, 4096).astype(np.float32)
    w = WebServer(lambda: {"version": "x", "freq": 145.57e6, "mode": "NFM", "aprs": []},
                  lambda: (spec, 145.6e6, 1_200_000), lan=lan, port=port)
    w.start()
    time.sleep(0.2)
    return w


def test_local_state_spectrum_page_and_audio_stream():
    w = _server()
    base = f"http://127.0.0.1:{w.port}"
    st, body, _ = _get(base + "/")
    assert st == 200 and b"PT2VHF SDR Tool" in body
    st, body, _ = _get(base + "/state")
    assert json.loads(body)["freq"] == 145.57e6
    st, body, _ = _get(base + "/spectrum")
    d = json.loads(body)
    assert d["c"] == 145.6e6 and len(d["db"]) == 1024
    # áudio: o motor empurra 48 kHz e o navegador recebe PCM 16 kHz
    stop = threading.Event()

    def feed():
        t = 0
        while not stop.is_set():
            w.audio.push((0.5 * np.sin(2 * np.pi * 1000 * (t + np.arange(4800)) / 48000)).astype(np.float32))
            t += 4800
            time.sleep(0.05)
    threading.Thread(target=feed, daemon=True).start()
    req = urllib.request.Request(base + "/audio")
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.headers["X-Audio-Format"].startswith("s16le;rate=16000")
        data = r.read(32000)  # ~1 s de áudio
    stop.set()
    pcm = np.frombuffer(data[: len(data) // 2 * 2], "<i2").astype(float)
    spec = np.abs(np.fft.rfft(pcm[2000:] * np.hanning(len(pcm) - 2000)))
    assert abs(np.argmax(spec) * 16000 / (len(pcm) - 2000) - 1000) < 30
    w.stop()


def test_lan_requires_key():
    ip = detect_lan_ipv4()
    if ip.startswith("127."):
        pytest.skip("sem interface de rede")
    w = _server(lan=True)
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(f"http://{ip}:{w.port}/state")
        assert e.value.code == 403
        st, _, hdr = _get(f"http://{ip}:{w.port}/?key={w.key}")
        cookie = hdr["Set-Cookie"].split(";")[0]
        st, body, _ = _get(f"http://{ip}:{w.port}/state", {"Cookie": cookie})
        assert st == 200 and json.loads(body)["mode"] == "NFM"
    finally:
        w.stop()
