"""Testes determinísticos dos feeds locais e do CAT da versão 0.8.0."""
import json
import socketserver
import threading

import pytest

from pt2vhf.rigctl import RigCtlClient, RigCtlError
from pt2vhf.traffic import (AISDecoder, export_csv, export_map, load_traffic,
                           parse_adsb, parse_radiosondes)


def _ais_nmea(typ=1, mmsi=123456789, lat=-15.8, lon=-47.9, speed=12.3):
    bits = ["0"] * 168

    def setbits(start, size, val):
        if val < 0:
            val = (1 << size) + val
        bits[start:start + size] = list(f"{val:0{size}b}")

    setbits(0, 6, typ)
    setbits(8, 30, mmsi)
    setbits(50, 10, round(speed * 10))
    setbits(61, 28, round(lon * 600000))
    setbits(89, 27, round(lat * 600000))
    setbits(116, 12, 1234)
    data = "".join(bits)
    text = "".join(chr(int(data[i:i + 6], 2) + 48 +
                       (8 if int(data[i:i + 6], 2) >= 40 else 0))
                   for i in range(0, len(data), 6))
    body = "!AIVDM,1,1,,A," + text + ",0"
    checksum = 0
    for c in body[1:]:
        checksum ^= ord(c)
    return f"{body}*{checksum:02X}"


def test_adsb_aircraft_json(tmp_path):
    data = {"now": 1731000000, "aircraft": [
        {"hex": "e49012", "flight": "TAM1234 ", "lat": -15.8, "lon": -47.9,
         "alt_baro": 10000, "gs": 200, "track": 180, "seen_pos": 2},
        {"hex": "outdated", "lat": -15, "lon": -47, "seen_pos": 180},
        {"hex": "invalid", "lat": 100, "lon": 0},
    ]}
    path = tmp_path / "aircraft.json"
    path.write_text(json.dumps(data))
    planes = load_traffic(path, "ADS-B")
    assert len(planes) == 1
    assert planes[0].ident == "E49012"
    assert planes[0].label == "TAM1234"
    assert planes[0].altitude_m == 3048
    assert planes[0].speed_kmh == 370.4


def test_radiosondes_import_and_projection_is_not_claimed(tmp_path):
    records = parse_radiosondes({"sondes": [
        {"id": "RS41-S123", "lat": -15.83, "lon": -47.91, "alt": 28000,
         "vel_v": -5.2, "vel_h": 12.0, "temp": -45, "humidity": 16},
        {"id": "broken", "lat": "nan", "lon": 0},
    ]}, now=1731000000)
    assert len(records) == 1
    assert records[0].vertical_ms == -5.2
    assert records[0].speed_kmh == 43.2
    assert "descida" in records[0].details
    p = tmp_path / "sonda.csv"
    export_csv(records, p)
    assert "RS41-S123" in p.read_text(encoding="utf-8-sig")


def test_ais_nmea_checksum_position_and_file(tmp_path):
    nmea = _ais_nmea()
    d = AISDecoder()
    assert d.ingest(nmea.replace("*", "*00", 1)) is None  # checksum inválido
    position = d.ingest(nmea)
    assert position is not None
    assert position.ident == "123456789"
    assert position.lat == pytest.approx(-15.8)
    assert position.lon == pytest.approx(-47.9)
    assert position.speed_kmh == pytest.approx(round(12.3 * 1.852, 1))
    path = tmp_path / "ais.nmea"
    path.write_text(nmea + "\n")
    assert load_traffic(path, "AIS")[0].ident == "123456789"


def test_map_html_escapes_source_text(tmp_path):
    rec = parse_radiosondes([{"id": "</script><script>alert(1)</script>",
                              "lat": 1, "lon": 2}])
    html = export_map(rec, tmp_path / "mapa.html").read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c" in html
    assert "openstreetmap.org" in html


class _RigHandler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline().decode().strip()
        self.server.received.append(line)
        if line == "f":
            self.wfile.write(b"145570000\n")
        elif line == "m":
            self.wfile.write(b"FM\n12000\n")
        else:
            self.wfile.write(b"RPRT 0\n")


def test_hamlib_tcp_get_and_set():
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    srv = Server(("127.0.0.1", 0), _RigHandler)
    srv.received = []
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        cat = RigCtlClient("127.0.0.1", srv.server_address[1], timeout=1)
        assert cat.read() == (145570000.0, "NFM")
        cat.write(145570000, "USB")
        assert srv.received == ["f", "m", "F 145570000", "M USB 0"]
        with pytest.raises(ValueError):
            cat.write(145570000, "RAW")
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=2)


def test_reject_bad_cat_and_unknown_traffic(tmp_path):
    with pytest.raises(ValueError):
        RigCtlClient("localhost", 0)
    path = tmp_path / "test.json"
    path.write_text("{}")
    with pytest.raises(ValueError):
        load_traffic(path, "other")
    with pytest.raises(ValueError):
        parse_adsb([])
