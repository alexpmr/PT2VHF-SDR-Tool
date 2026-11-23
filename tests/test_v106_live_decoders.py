"""ADS-B (nativo), AIS (AIS-catcher embarcado) e ACARS (nativo) pelo IQ do SDR atual.

Sinais sintéticos e vetores públicos de Mode S: provam a cadeia de software, não
substituem recepção RF real (homologação pendente).
"""
from __future__ import annotations

import os
import socket
import struct
import time

import numpy as np
import pytest

from pt2vhf.decoders import acars as A
from pt2vhf.decoders import modes as M
from pt2vhf import ais_rx

IDENT = bytes.fromhex("8D4840D6202CC371C32CE0576098")
POS_ODD = bytes.fromhex("8D40621D58C386435CC412692AD6")
POS_EVEN = bytes.fromhex("8D40621D58C382D690C8AC2863A7")
VELOCITY = bytes.fromhex("8D485020994409940838175B284F")
VECTORS = [IDENT, POS_ODD, POS_EVEN, VELOCITY]


# ------------------------------------------------------------------ ADS-B
def test_modes_public_vectors_decode():
    assert all(M.residual(m) == 0 for m in VECTORS)
    dec = M.ADSBDecoder()
    for i, msg in enumerate(VECTORS):
        dec.ingest(msg, now=1000.0 + i)
    snap = dec.snapshot(now=1004.0)
    planes = {a["hex"]: a for a in snap["aircraft"]}
    assert planes["4840D6"]["flight"] == "KLM1023"
    assert planes["40621D"]["alt_baro"] == 38000
    assert abs(planes["40621D"]["lat"] - 52.2572) < 1e-4
    assert abs(planes["40621D"]["lon"] - 3.91937) < 1e-4
    assert planes["485020"]["gs"] == pytest.approx(159.2, abs=0.1)
    assert planes["485020"]["track"] == pytest.approx(182.88, abs=0.1)
    assert planes["485020"]["baro_rate"] == -832
    from pt2vhf.traffic import parse_adsb
    tracks = parse_adsb(snap, now=1004.0)
    assert [t.ident for t in tracks] == ["40621D"]


def test_modes_single_bit_correction_and_rejection():
    broken = bytearray(IDENT)
    broken[6] ^= 0x10
    assert M.correct_single_bit(bytes(broken)) == IDENT
    broken[9] ^= 0x01
    assert M.correct_single_bit(bytes(broken)) is None


@pytest.mark.parametrize("rate", [2_400_000, 2_880_000])
def test_modes_demodulator_on_synthetic_iq(rate):
    iq = M.synth_adsb_iq(VECTORS * 3, rate, snr_db=20, freq_offset_hz=150e3, seed=3)
    demod, out = M.ModeSDemodulator(rate), []
    for i in range(0, iq.size, 40_000):          # blocos que cortam quadros ao meio
        out += demod.process(iq[i:i + 40_000])
    out += demod.process(np.zeros(20_000, np.complex64))
    assert len(out) == 12 and all(m in VECTORS for m in out)


def test_modes_requires_24_msps_and_noise_has_no_frames():
    with pytest.raises(ValueError):
        M.ModeSDemodulator(1_920_000)
    rng = np.random.default_rng(7)
    noise = (0.01 * (rng.standard_normal(1_200_000) + 1j * rng.standard_normal(1_200_000))).astype(np.complex64)
    assert M.ModeSDemodulator(2_400_000).process(noise) == []


def test_adsb_receiver_thread_publishes_snapshot():
    snaps = []
    rx = M.ADSBReceiver(2_400_000, snaps.append)
    rx.start()
    try:
        iq = M.synth_adsb_iq([IDENT, POS_ODD, POS_EVEN], 2_400_000, snr_db=25)
        rx.feed(iq, M.ADSB_FREQ_HZ, 2_400_000)
        rx.feed(np.zeros(50_000, np.complex64), M.ADSB_FREQ_HZ, 2_400_000)
        rx.feed(iq, 145e6, 2_400_000)             # SDR fora de 1090 MHz: descartado
        deadline = time.time() + 5
        while not snaps and time.time() < deadline:
            time.sleep(0.05)
    finally:
        rx.stop()
    assert snaps and {a["hex"] for a in snaps[-1]["aircraft"]} >= {"4840D6", "40621D"}
    assert rx.diagnostics()["dropped"] == 1


# ------------------------------------------------------------------ ACARS
def test_acars_block_roundtrip_audio():
    blocks = [A.build_block(text="M01APT2VHFTESTE ACARS"), A.build_block(label="Q0", block_id="2")]
    demod = A.AcarsDemodulator()
    audio = A.synth_acars_audio(blocks)
    msgs = []
    for i in range(0, audio.size, 4800):
        msgs += demod.process(audio[i:i + 4800])
    msgs += demod.flush()
    by_label = {m["label"]: m for m in msgs}
    assert set(by_label) == {"H1", "Q0"}
    assert by_label["H1"]["reg"] == "PP-XYZ" and by_label["H1"]["flight"] == "PT2VHF"
    assert by_label["H1"]["msg_no"] == "M01A" and by_label["H1"]["text"] == "TESTE ACARS"


def test_acars_rejects_bad_crc_and_fixes_one_parity_error():
    block = A.build_block(text="M01APT2VHFOK")
    body_start = 16 + 5
    end = block.index(0x83, body_start)
    body, crc = block[body_start:end + 1], block[end + 1:end + 3]
    assert A.parse_block(body, crc)["text"] == "OK"
    assert A.parse_block(body, bytes((crc[0] ^ 1, crc[1]))) is None
    damaged = bytearray(body)
    damaged[3] ^= 0x04
    assert A.parse_block(bytes(damaged), crc) is None
    assert A._fix_one_char(bytes(damaged), crc)["text"] == "OK"


def test_acars_receiver_decodes_all_three_channels_from_iq():
    rate, center = 2_400_000, 131_850_000
    got = []
    rx = A.AcarsReceiver(rate, got.append)
    rx.start()
    try:
        for k, freq in enumerate(A.ACARS_FREQS_HZ):
            iq = A.synth_acars_iq([A.build_block(text=f"M0{k}APT2VHFCANAL{k}")], rate, center,
                                  station_hz=freq, snr_db=20, seed=k)
            iq = np.concatenate((iq, np.full(int(2.5 * rate), 0.25, np.complex64)))
            for i in range(0, iq.size, 240_000):
                while rx._queue.full():
                    time.sleep(0.01)
                rx.feed(iq[i:i + 240_000], center, rate)
        deadline = time.time() + 20
        while len(got) < 3 and time.time() < deadline:
            time.sleep(0.1)
    finally:
        rx.stop()
    assert {(m["freq_mhz"], m["text"]) for m in got} == {
        (131.55, "CANAL0"), (131.725, "CANAL1"), (131.825, "CANAL2")}


# ------------------------------------------------------------------ AIS
def test_ais_frame_has_valid_hdlc_crc():
    bits = ais_rx.ais_position_bits(710000001, -23.0, -43.2, 12.3, 45.6)
    assert len(bits) == 168
    data = bytes(int(bits[i:i + 8], 2) for i in range(0, 168, 8))
    crc = ais_rx._crc16_x25(data)
    # Resíduo X.25 com o FCS anexado (LSB primeiro) é a constante 0xF0B8 ^ 0xFFFF.
    assert ais_rx._crc16_x25(data + bytes((crc & 0xFF, crc >> 8))) == 0x0F47
    assert set(np.unique(ais_rx.ais_frame_bits(bits))) <= {0, 1}


def test_ais_command_and_cu8_conversion():
    cmd = ais_rx.build_ais_command("AIS-catcher", 12345)
    assert cmd[1:4] == ["-t", "127.0.0.1", "12345"] and "-s" in cmd and "288000" in cmd
    cu8 = np.frombuffer(ais_rx.to_cu8(np.array([1 + 1j, -1 - 1j, 0j], np.complex64), 1.0), np.uint8)
    assert list(cu8) == [255, 255, 0, 0, 128, 128]


def test_local_iq_server_speaks_rtl_tcp_on_loopback_only():
    server = ais_rx.LocalIQServer(timeout=5)
    try:
        assert server.sock.getsockname()[0] == "127.0.0.1"
        client = socket.create_connection(("127.0.0.1", server.port), timeout=5)
        server.accept()
        client.sendall(bytes((1,)) + struct.pack(">I", 162_000_000))   # comando ignorado
        assert client.recv(12) == b"RTL0" + struct.pack(">II", 5, 29)
        server.send(b"\x80\x80")
        assert client.recv(2) == b"\x80\x80"
        client.close()
    finally:
        server.close()


@pytest.mark.skipif(not ais_rx.find_ais_catcher()[0],
                    reason="AIS-catcher não preparado (packaging/prepare_ais_catcher.sh native)")
def test_ais_catcher_end_to_end_synthetic():
    ships = {t.ident: t for t in ais_rx.synthetic_ais_check()}
    assert set(ships) == {"710000001", "710000002", "710000003"}
    assert ships["710000002"].lat == pytest.approx(-23.01) and ships["710000002"].lon == pytest.approx(-43.2)
    assert ships["710000001"].course_deg == pytest.approx(45.6)


def test_packaging_declares_ais_catcher_bundle():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = open(os.path.join(root, "packaging", "prepare_ais_catcher.sh"), encoding="utf-8").read()
    assert "BIN_SHA256=" in script and "git -C" in script and "archive" in script
    spec = open(os.path.join(root, "pt2vhf.spec"), encoding="utf-8").read()
    assert '"ais_catcher"' in spec and '"sonde_decoders"' in spec


# ------------------------------------------------------------------ interface
def test_live_controls_and_acars_panel(qt_lifecycle, tmp_path):
    from pt2vhf.config import Config
    from pt2vhf.ui.acars_panel import AcarsPanel
    from pt2vhf.ui.traffic_panel import SourceTab
    cfg = Config(tmp_path / "config.json")
    adsb, sonde = SourceTab("ADS-B", cfg), SourceTab("Sonda", cfg)
    assert hasattr(adsb, "live_start") and not hasattr(sonde, "live_start")
    seen = []
    adsb.liveStartRequested.connect(seen.append)
    adsb.live_start.click()
    assert seen == ["ADS-B"]
    adsb.live_running(True)
    assert adsb.live_stop.isEnabled() and not adsb.live_start.isEnabled()
    panel = AcarsPanel()
    panel.add_message({"freq_mhz": 131.55, "reg": "PP-XYZ", "flight": "PT2VHF", "label": "H1",
                       "block_id": "1", "msg_no": "M01A", "text": "OLA", "timestamp": 0})
    assert panel.table.rowCount() == 1 and panel.table.item(0, 2).text() == "PP-XYZ"
    for w in (adsb, sonde, panel):
        w.close()


def test_main_window_live_mode_one_at_a_time(tmp_path, monkeypatch, qt_lifecycle):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from pt2vhf.ui.main_window import MainWindow
    w = MainWindow()
    try:
        w._start_live("ACARS")                       # SDR desligado
        assert "Ligue primeiro" in w.acars_panel.status.text() and w.live_worker is None
        w.rx_panel.source.setCurrentText("Simulador")
        w.rx_panel.start_btn.setChecked(True)
        assert w.engine.running
        w._start_live("AIS")
        assert "receptor físico" in w.ais_panel.live_status.text()
        w.cfg["source"] = "Gravação IQ"               # simula fonte não-simulador
        w._start_live("ACARS")
        assert w.live_kind == "ACARS" and w.live_worker.feed in w.engine.iq_listeners
        assert w.mode == "AM" and abs(w.engine.vfo - A.ACARS_FREQS_HZ[0]) < 1
        assert w.acars_panel.stop.isEnabled()
        w._handle_live_event("live_acars", {"freq_mhz": 131.55, "reg": "PP-ABC", "text": "X"})
        assert w.acars_panel.table.item(0, 2).text() == "PP-ABC"
        worker = w.live_worker
        w._start_live("ACARS")                        # reinício troca o worker
        assert w.live_worker is not worker and worker.feed not in w.engine.iq_listeners
        w._stop_live()
        assert w.live_worker is None and not w.acars_panel.stop.isEnabled()
    finally:
        w.close()
    assert not w.engine.running
