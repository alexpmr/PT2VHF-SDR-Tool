"""Tráfego ADS-B (dump1090/readsb), AIS (NMEA VDM) e radiossondas (JSON local).

A aquisição/decodificação RF pertence a processos externos: readsb/dump1090,
rtl_ais/AIS-catcher e radiosonde_auto_rx. Não há promessa de demodulação IQ.
Nenhuma conexão é feita a servidores públicos ou serviços de terceiros.
"""
from __future__ import annotations

import csv
import html
from collections import defaultdict
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Track:
    source: str
    ident: str
    lat: float
    lon: float
    label: str = ""
    altitude_m: float | None = None
    speed_kmh: float | None = None
    course_deg: float | None = None
    vertical_ms: float | None = None
    timestamp: float = 0.0
    details: str = ""

    def __post_init__(self):
        self.lat = float(self.lat)
        self.lon = float(self.lon)
        if not (math.isfinite(self.lat) and math.isfinite(self.lon)
                and -90 <= self.lat <= 90 and -180 <= self.lon <= 180):
            raise ValueError("Coordenadas geográficas inválidas")
        if not self.timestamp:
            self.timestamp = time.time()


def _num(v):
    if v is None or isinstance(v, bool) or v == "":
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def parse_adsb(data: dict, now: float | None = None) -> list[Track]:
    """JSON aircraft.json de readsb/dump1090: velocidade em nós, altitude em pés."""
    if not isinstance(data, dict):
        raise ValueError("ADS-B: esperava objeto JSON")
    now = time.time() if now is None else now
    stamp = _num(data.get("now")) or now
    out = []
    for a in data.get("aircraft", []):
        if not isinstance(a, dict):
            continue
        lat, lon = _num(a.get("lat")), _num(a.get("lon"))
        if lat is None or lon is None:
            continue
        age = _num(a.get("seen_pos"))
        if age is not None and (age < 0 or age > 120):
            continue
        ident = str(a.get("hex") or "").strip().upper()
        if not ident or len(ident) > 12:
            continue
        flight = str(a.get("flight") or "").strip()
        alt_ft = _num(a.get("alt_geom"))
        if alt_ft is None:
            alt_ft = _num(a.get("alt_baro"))
        speed_knots = _num(a.get("gs"))
        try:
            out.append(Track("ADS-B", ident, lat, lon, flight or ident,
                             altitude_m=round(alt_ft * 0.3048) if alt_ft is not None else None,
                             speed_kmh=round(speed_knots * 1.852, 1) if speed_knots is not None else None,
                             course_deg=_num(a.get("track")),
                             timestamp=stamp - (age or 0),
                             details="ICAO " + ident))
        except ValueError:
            continue
    return out


def parse_radiosondes(data, now: float | None = None) -> list[Track]:
    """Importa amostras JSON locais geradas por auto_rx ou conversores de telemetria."""
    now = time.time() if now is None else now
    if isinstance(data, dict):
        values = data.get("sondes", data.get("telemetry", [data]))
        if isinstance(values, dict):
            values = list(values.values())
    elif isinstance(data, list):
        values = data
    else:
        raise ValueError("Radiossondas: formato JSON inválido")
    if not isinstance(values, list):
        raise ValueError("Radiossondas: lista de amostras inválida")
    out = []
    for a in values:
        if not isinstance(a, dict):
            continue
        lat, lon = _num(a.get("lat", a.get("latitude"))), _num(a.get("lon", a.get("longitude")))
        if lat is None or lon is None:
            continue
        ident = str(a.get("id") or a.get("serial") or a.get("sonde_id") or "").strip()
        if not ident:
            continue
        alt = _num(a.get("alt", a.get("altitude")))
        vertical = _num(a.get("vel_v", a.get("ascent_rate")))
        horizontal = _num(a.get("vel_h", a.get("speed")))
        heading = _num(a.get("heading", a.get("course")))
        stamp = _num(a.get("timestamp")) or now
        phase = "subida" if vertical is not None and vertical > 0.3 else (
            "descida" if vertical is not None and vertical < -0.3 else "sem fase")
        extra = []
        for key, label in (("temp", "T"), ("humidity", "UR"), ("pressure", "P"),
                           ("batt", "Bat"), ("freq", "MHz"), ("type", "Modelo")):
            val = a.get(key)
            if val is not None:
                extra.append(f"{label}={val}")
        try:
            out.append(Track("Sonda", ident, lat, lon, ident, alt,
                             horizontal * 3.6 if horizontal is not None else None,
                             heading, vertical, stamp, phase + " · " + " ".join(extra)))
        except ValueError:
            continue
    return out


_AIS_CHARS = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?"


def _signed(bits: str) -> int:
    n = int(bits, 2)
    return n - (1 << len(bits)) if bits and bits[0] == "1" else n


def _ais_bits(payload: str, fill: int = 0) -> str:
    bits = []
    for char in payload:
        value = ord(char) - 48
        if value > 40:
            value -= 8
        if not 0 <= value <= 63:
            raise ValueError("Caractere AIS inválido")
        bits.append(f"{value:06b}")
    result = "".join(bits)
    return result[:-fill] if fill else result


def _ais_text(bits: str) -> str:
    return "".join(_AIS_CHARS[int(bits[i:i + 6], 2)] for i in range(0, len(bits) - 5, 6)).strip("@ ")


class AISDecoder:
    """Decodifica mensagens AIS NMEA VDM tipo 1/2/3/18/19 e nomes do tipo 5."""
    def __init__(self):
        self.fragments = {}
        self.names: dict[str, str] = {}
        self.tracks: dict[str, Track] = {}

    def ingest(self, line: str, now: float | None = None) -> Track | None:
        raw = line.strip()
        if not raw.startswith(("!AIVDM,", "!AIVDO,", "!BSVDM,")):
            return None
        body, star, checksum = raw.partition("*")
        if star:
            expected = 0
            for char in body[1:]:
                expected ^= ord(char)
            try:
                if int(checksum[:2], 16) != expected:
                    return None
            except ValueError:
                return None
        parts = body.split(",")
        if len(parts) < 7:
            return None
        try:
            count, number = int(parts[1]), int(parts[2])
            fill = int(parts[6])
        except ValueError:
            return None
        if not 1 <= count <= 9 or not 1 <= number <= count or not 0 <= fill <= 5:
            return None
        payload = parts[5]
        if count != 1:
            key = (parts[0], parts[3], parts[4], count)
            old = self.fragments.get(key, {})
            if number == 1:
                old = {}
            old[number] = (payload, fill)
            self.fragments[key] = old
            if len(self.fragments) > 100:
                self.fragments.clear()
                return None
            if len(old) != count:
                return None
            payload = "".join(old[i][0] for i in range(1, count + 1))
            fill = old[count][1]
            del self.fragments[key]
        bits = _ais_bits(payload, fill)
        if len(bits) < 38:
            return None
        typ = int(bits[:6], 2)
        mmsi = str(int(bits[8:38], 2))
        if typ == 5 and len(bits) >= 232:
            self.names[mmsi] = _ais_text(bits[112:232]) or mmsi
            if mmsi in self.tracks:
                self.tracks[mmsi].label = self.names[mmsi]
            return None
        if typ in (1, 2, 3) and len(bits) >= 128:
            speed, lon, lat, course = (int(bits[50:60], 2), _signed(bits[61:89]),
                                       _signed(bits[89:116]), int(bits[116:128], 2))
        elif typ in (18, 19) and len(bits) >= 124:
            speed, lon, lat, course = (int(bits[46:56], 2), _signed(bits[57:85]),
                                       _signed(bits[85:112]), int(bits[112:124], 2))
        else:
            return None
        if abs(lon) >= 108600000 or abs(lat) >= 54600000:
            return None
        try:
            record = Track("AIS", mmsi, lat / 600000, lon / 600000,
                           self.names.get(mmsi, mmsi),
                           speed_kmh=round(speed / 10 * 1.852, 1) if speed < 1023 else None,
                           course_deg=course / 10 if course < 3600 else None,
                           timestamp=now or time.time(),
                           details=f"MMSI {mmsi} · classe {typ}")
        except ValueError:
            return None
        self.tracks[mmsi] = record
        return record


def parse_ais(lines: str, now: float | None = None) -> list[Track]:
    dec = AISDecoder()
    for line in lines.splitlines():
        dec.ingest(line, now)
    return list(dec.tracks.values())


def load_traffic(path: str | Path, kind: str) -> list[Track]:
    """Lê arquivos produzidos por decodificadores externos; nunca executa software externo."""
    file = Path(path).expanduser()
    if not file.is_file():
        raise FileNotFoundError(str(file))
    if kind == "AIS":
        # Apenas cauda do log; em arquivo muito grande evita bloquear a GUI.
        with file.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 2_000_000))
            data = f.read().decode("utf-8", errors="replace")
        if size > 2_000_000:
            data = data.partition("\n")[2]
        return parse_ais(data)
    if file.stat().st_size > 8_000_000:
        raise ValueError("JSON maior que 8 MB: configure rotação no decodificador externo")
    data = json.loads(file.read_text(encoding="utf-8"))
    if kind == "ADS-B":
        return parse_adsb(data)
    if kind == "Sonda":
        return parse_radiosondes(data)
    raise ValueError("Tipo de tráfego desconhecido")


def export_csv(tracks: list[Track], path: str | Path):
    if not tracks:
        raise ValueError("Sem registros para exportar")
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(tracks[0])))
        writer.writeheader()
        writer.writerows(asdict(x) for x in tracks)


def export_map(tracks: list[Track], path: str | Path):
    """Mapa HTML OSM/Leaflet por arquivo: requer Internet para os tiles do mapa."""
    valid = tracks[:2000]
    payload = json.dumps([asdict(x) for x in valid], ensure_ascii=False).replace("<", "\\u003c")
    title = html.escape("PT2VHF · Tráfego aéreo, marítimo e radiossondas")
    page = f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>{title}</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>body{{margin:0;background:#111a22;color:#eee;font:14px sans-serif}}
#map{{height:94vh}}header{{padding:12px}}</style><header>{title} — {len(valid)} posições</header>
<div id="map"></div><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>const data={payload};
const map=L.map("map").setView([-15.8,-47.9],5);
L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",{{attribution:"© OpenStreetMap"}}).addTo(map);
const group=L.featureGroup().addTo(map);
const history=new Map();
for(const p of data){{
  const key=p.source+"/"+p.ident;
  if(!history.has(key))history.set(key,[]);
  history.get(key).push(p);
}}
for(const positions of history.values()){{
  positions.sort((a,b)=>a.timestamp-b.timestamp);
  const p=positions[positions.length-1];
  if(positions.length>1){{
    const segment=positions.map(r=>[r.lat,r.lon]);
    L.polyline(segment,{{weight:3,opacity:.75}}).addTo(group);
  }}
  const m=L.marker([p.lat,p.lon]).addTo(group);
  const node=document.createElement("div");
  for(const [k,v] of Object.entries({{Tipo:p.source,ID:p.ident,Nome:p.label,
    Altitude_m:p.altitude_m,Vel_kmh:p.speed_kmh,Rumo:p.course_deg,Detalhes:p.details}})){{
    if(v===null||v===undefined)continue;
    const item=document.createElement("div"); item.textContent=k+": "+v; node.appendChild(item);
  }} m.bindPopup(node);
}}
if(group.getLayers().length)map.fitBounds(group.getBounds().pad(.2),{{maxZoom:11}});
</script></html>"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def export_gpx(tracks: list[Track], path: str | Path):
    """Exporta trajetórias para GPX 1.1 por estação; campos escapados para XML."""
    groups = defaultdict(list)
    for item in tracks:
        groups[(item.source, item.ident)].append(item)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<gpx version="1.1" creator="PT2VHF SDR Tool" xmlns="http://www.topografix.com/GPX/1/1">']
    for (source, ident), positions in sorted(groups.items()):
        lines.append("<trk><name>" + xml_escape(source + " " + ident) + "</name><trkseg>")
        for pos in sorted(positions, key=lambda x: x.timestamp):
            stamp = datetime.fromtimestamp(pos.timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
            elevation = f"<ele>{pos.altitude_m:.2f}</ele>" if pos.altitude_m is not None else ""
            lines.append(f'<trkpt lat="{pos.lat:.7f}" lon="{pos.lon:.7f}">{elevation}'
                         f'<time>{stamp}</time></trkpt>')
        lines.append("</trkseg></trk>")
    lines.append("</gpx>")
    out = Path(path)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def export_kml(tracks: list[Track], path: str | Path):
    """Exporta rastros em KML com grupos por indicativo/MMSI/número de série."""
    groups = defaultdict(list)
    for item in tracks:
        groups[(item.source, item.ident)].append(item)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
    for (source, ident), positions in sorted(groups.items()):
        coords = " ".join(f"{p.lon:.7f},{p.lat:.7f},{p.altitude_m or 0:.1f}"
                          for p in sorted(positions, key=lambda x: x.timestamp))
        lines.extend(["<Placemark><name>" + xml_escape(source + " " + ident) + "</name>",
                      "<LineString><tessellate>1</tessellate><coordinates>" + coords +
                      "</coordinates></LineString></Placemark>"])
    lines.append("</Document></kml>")
    out = Path(path)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
