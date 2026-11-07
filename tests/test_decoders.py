import numpy as np

from pt2vhf.decoders import aprs
from pt2vhf.decoders.afsk import AFSKDemodulator, afsk_modulate
from pt2vhf.decoders.ax25 import AX25Frame, build_frame, crc16_x25, parse_frame
from pt2vhf.decoders.tones import CTCSSDetector, DTMFDecoder


def test_crc_known_value():
    assert crc16_x25(b"123456789") == 0x906E


def test_ax25_roundtrip():
    f = AX25Frame("PY2ABC-9", "APRS", ["WIDE1-1", "WIDE2-1*"], b">teste")
    g = parse_frame(build_frame(f))
    assert g.tnc2() == "PY2ABC-9>APRS,WIDE1-1,WIDE2-1*:>teste"


def test_afsk_roundtrip_with_noise():
    f = AX25Frame("PY2ABC-9", "APRS", ["WIDE1-1"], b"!2330.00S/04637.00W>Teste")
    a = afsk_modulate(f)
    a = np.concatenate([np.zeros(4800, np.float32), a, np.zeros(4800, np.float32)])
    a += np.random.default_rng(1).normal(0, 0.25, len(a)).astype(np.float32)
    got = []
    d = AFSKDemodulator(got.append)
    for i in range(0, len(a), 3000):
        d.process(a[i:i + 3000])
    assert [g.tnc2() for g in got] == [f.tnc2()]


def test_aprs_formats():
    p = aprs.parse(AX25Frame("A", "APRS", [], b"!2332.55S/04638.07W>090/036/A=002500 x"))
    assert p.type == "Posição"
    assert abs(p.lat + 23.5425) < 1e-4 and abs(p.lon + 46.6345) < 1e-4
    assert p.course == 90 and round(p.speed_kmh) == 67 and round(p.altitude_m) == 762

    p = aprs.parse(AX25Frame("B", "RSS25U", [], b"`JB#oXv>/Mic-E"))
    assert p.type == "Mic-E"
    assert abs(p.lat + 23.5425) < 1e-4 and abs(p.lon + 46.6345) < 1e-4
    assert p.course == 90

    p = aprs.parse(AX25Frame("C", "APRS", [], b"=/5L!!<*e7>7P["))  # compactada (exemplo da spec)
    assert abs(p.lat - 49.5) < 0.01 and abs(p.lon + 72.75) < 0.01

    p = aprs.parse(AX25Frame("D", "APRS", [], b"T#005,199,000,255,073,123,01101001"))
    assert p.type == "Telemetria" and p.telemetry["A1"] == 199

    p = aprs.parse(AX25Frame("E", "APRS", [], b":PY2XYZ   :Ola{01"))
    assert p.message_to == "PY2XYZ" and p.message == "Ola"


def test_locator():
    assert aprs.maidenhead(-23.5425, -46.6345)[:4] == "GG66"
    lat, lon = aprs.locator_to_latlon("GG66qk")
    assert abs(lat + 23.5) < 0.1 and abs(lon + 46.6) < 0.1


def _tones(freqs, dur, fs=48000, amp=0.3):
    t = np.arange(int(dur * fs)) / fs
    return sum(amp * np.sin(2 * np.pi * f * t) for f in freqs).astype(np.float32)


def test_dtmf():
    keys = {"1": (697, 1209), "5": (770, 1336), "9": (852, 1477), "#": (941, 1477), "D": (941, 1633)}
    sig = np.concatenate([np.concatenate([_tones(keys[k], 0.12), np.zeros(4800, np.float32)])
                          for k in "159#D"])
    got = []
    d = DTMFDecoder(got.append)
    for i in range(0, len(sig), 2400):
        d.process(sig[i:i + 2400])
    assert "".join(got) == "159#D"


def test_ctcss():
    sig = _tones([88.5], 2.0, amp=0.1) + _tones([1000], 2.0, amp=0.5)
    det = CTCSSDetector()
    tone = None
    for i in range(0, len(sig), 4800):
        tone = det.process(sig[i:i + 4800])
    assert tone == 88.5
