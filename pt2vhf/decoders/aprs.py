"""Parser APRS: posições (normal, compactada, Mic-E), status, mensagens, telemetria, clima."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .ax25 import AX25Frame


@dataclass
class APRSPacket:
    source: str
    dest: str
    path: str
    raw: str
    type: str = "Outro"
    lat: float | None = None
    lon: float | None = None
    symbol: str = ""
    comment: str = ""
    speed_kmh: float | None = None
    course: int | None = None
    altitude_m: float | None = None
    message_to: str = ""
    message: str = ""
    telemetry: dict = field(default_factory=dict)
    weather: dict = field(default_factory=dict)

    def position_str(self) -> str:
        if self.lat is None or self.lon is None:
            return ""
        return f"{abs(self.lat):.4f}°{'N' if self.lat >= 0 else 'S'} " \
               f"{abs(self.lon):.4f}°{'E' if self.lon >= 0 else 'W'}"


def _parse_uncompressed(s: str):
    m = re.match(r"(\d{2})([\d ]{2}\.[\d ]{2})([NS])(.)(\d{3})([\d ]{2}\.[\d ]{2})([EW])(.)", s)
    if not m:
        return None
    lat = int(m.group(1)) + float(m.group(2).replace(" ", "0")) / 60
    lon = int(m.group(5)) + float(m.group(6).replace(" ", "0")) / 60
    if m.group(3) == "S":
        lat = -lat
    if m.group(7) == "W":
        lon = -lon
    return lat, lon, m.group(4) + m.group(8), s[19:]


def _b91(s: str) -> int:
    v = 0
    for c in s:
        v = v * 91 + (ord(c) - 33)
    return v


def _parse_compressed(s: str):
    if len(s) < 13:
        return None
    lat = 90 - _b91(s[1:5]) / 380926.0
    lon = -180 + _b91(s[5:9]) / 190463.0
    sym = s[0] + s[9]
    extra = {}
    cs = s[10:12]
    if cs[0] != " ":
        c, sp = ord(cs[0]) - 33, ord(cs[1]) - 33
        t = ord(s[12]) - 33
        if (t & 0x18) == 0x10:
            extra["alt"] = (1.002 ** (c * 91 + sp)) * 0.3048
        elif 0 <= c <= 89:
            extra["course"] = c * 4
            extra["speed"] = (1.08 ** sp - 1) * 1.852
    return lat, lon, sym, s[13:], extra


def _parse_mic_e(dest: str, info: str):
    """Decodifica Mic-E (destino codifica latitude; info codifica longitude/vel/curso)."""
    d = dest.split("-")[0].ljust(6)[:6]
    digits = []
    for c in d:
        if "0" <= c <= "9":
            digits.append(int(c))
        elif "A" <= c <= "J":
            digits.append(ord(c) - ord("A"))
        elif "P" <= c <= "Y":
            digits.append(ord(c) - ord("P"))
        else:  # K, L, Z = espaço
            digits.append(0)
    lat = digits[0] * 10 + digits[1] + (digits[2] * 10 + digits[3] + (digits[4] * 10 + digits[5]) / 100) / 60
    north = "P" <= d[3] <= "Z"
    lon_off = 100 if "P" <= d[4] <= "Z" else 0
    west = "P" <= d[5] <= "Z"
    if not north:
        lat = -lat
    if len(info) < 9:
        return None
    lon_deg = ord(info[1]) - 28 + lon_off
    if 180 <= lon_deg <= 189:
        lon_deg -= 80
    elif 190 <= lon_deg <= 199:
        lon_deg -= 190
    lon_min = ord(info[2]) - 28
    if lon_min >= 60:
        lon_min -= 60
    lon_hun = ord(info[3]) - 28
    lon = lon_deg + (lon_min + lon_hun / 100) / 60
    if west:
        lon = -lon
    sp = (ord(info[4]) - 28) * 10
    dc = ord(info[5]) - 28
    se = ord(info[6]) - 28
    speed = sp + dc // 10
    if speed >= 800:
        speed -= 800
    course = (dc % 10) * 100 + se
    if course >= 400:
        course -= 400
    sym = info[8] + info[7]
    comment = info[9:]
    alt = None
    m = re.search(r"(.{3})\}", comment)
    if m:
        alt = _b91(m.group(1)) - 10000
        comment = comment.replace(m.group(0), "")
    # remove prefixos de tipo de rádio (ex.: '`', ']', '>')
    comment = comment.lstrip("`'>]")
    return lat, lon, sym, comment, speed * 1.852, course, alt


def _parse_weather(s: str) -> dict:
    wx = {}
    for key, name, conv in (("c", "dir_vento", int), ("s", "vel_vento_mph", int),
                            ("g", "rajada_mph", int), ("t", "temp_F", int),
                            ("h", "umidade", int), ("b", "pressao_dPa", int),
                            ("r", "chuva_1h", int)):
        m = re.search(key + r"(-?\d{2,5})", s)
        if m:
            try:
                wx[name] = conv(m.group(1))
            except ValueError:
                pass
    if "temp_F" in wx:
        wx["temp_C"] = round((wx["temp_F"] - 32) * 5 / 9, 1)
    return wx


def parse(frame: AX25Frame) -> APRSPacket:
    info = frame.info.decode("latin-1", errors="replace")
    pkt = APRSPacket(frame.source, frame.dest, frame.path_str(), frame.tnc2())
    if not info:
        return pkt
    t = info[0]
    try:
        if t in "!=/@":
            body = info[1:]
            if t in "/@":
                body = body[7:]  # timestamp
            pkt.type = "Posição"
            if body[:1].isdigit():
                r = _parse_uncompressed(body)
                if r:
                    pkt.lat, pkt.lon, pkt.symbol, pkt.comment = r
            else:
                r = _parse_compressed(body)
                if r:
                    pkt.lat, pkt.lon, pkt.symbol, pkt.comment, extra = r
                    pkt.course = extra.get("course")
                    pkt.speed_kmh = extra.get("speed")
                    pkt.altitude_m = extra.get("alt")
            m = re.match(r"(\d{3})/(\d{3})", pkt.comment)
            if m:
                pkt.course, pkt.speed_kmh = int(m.group(1)), int(m.group(2)) * 1.852
                pkt.comment = pkt.comment[7:]
            m = re.search(r"/A=(-?\d{6})", pkt.comment)
            if m:
                pkt.altitude_m = int(m.group(1)) * 0.3048
            if pkt.symbol.endswith("_"):
                pkt.type = "Clima"
                pkt.weather = _parse_weather(pkt.comment)
                if pkt.course is not None:  # em estações WX, "ccc/sss" = vento
                    pkt.weather["dir_vento"] = pkt.course
                    pkt.weather["vel_vento_mph"] = round(pkt.speed_kmh / 1.852)
                    pkt.course = pkt.speed_kmh = None
        elif t in "`'\x1c\x1d":
            r = _parse_mic_e(frame.dest, info)
            if r:
                pkt.type = "Mic-E"
                pkt.lat, pkt.lon, pkt.symbol, pkt.comment, pkt.speed_kmh, pkt.course, pkt.altitude_m = r
        elif t == ">":
            pkt.type = "Status"
            pkt.comment = info[1:]
        elif t == ":":
            pkt.type = "Mensagem"
            pkt.message_to = info[1:10].strip()
            pkt.message = info[11:]
            if "{" in pkt.message:  # identificador da mensagem (ack)
                pkt.message = pkt.message.rsplit("{", 1)[0]
            if pkt.message.startswith(("PARM.", "UNIT.", "EQNS.", "BITS.")):
                pkt.type = "Telemetria (def.)"
        elif info.startswith("T#"):
            pkt.type = "Telemetria"
            parts = info[2:].split(",")
            pkt.telemetry = {"seq": parts[0]}
            for i, v in enumerate(parts[1:6]):
                try:
                    pkt.telemetry[f"A{i + 1}"] = float(v)
                except ValueError:
                    pass
            if len(parts) > 6:
                pkt.telemetry["bits"] = parts[6][:8]
                pkt.comment = parts[6][8:]
        elif t == "_":
            pkt.type = "Clima"
            pkt.weather = _parse_weather(info[9:])
        elif t == ";":
            pkt.type = "Objeto"
            pkt.message_to = info[1:10].strip()
            body = info[18:]
            r = _parse_uncompressed(body) if body[:1].isdigit() else _parse_compressed(body)
            if r:
                pkt.lat, pkt.lon, pkt.symbol, pkt.comment = r[:4]
        elif t == "}":
            pkt.type = "Terceiros"
            pkt.comment = info[1:]
        else:
            pkt.comment = info
    except (IndexError, ValueError):
        pkt.comment = info
    return pkt


def distance_bearing(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    """Distância (km) e azimute (graus) entre dois pontos."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * r * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


def maidenhead(lat: float, lon: float, precision: int = 6) -> str:
    lon += 180
    lat += 90
    s = chr(ord("A") + int(lon // 20)) + chr(ord("A") + int(lat // 10))
    s += str(int((lon % 20) // 2)) + str(int(lat % 10))
    if precision >= 6:
        s += chr(ord("a") + int((lon % 2) * 12)) + chr(ord("a") + int((lat % 1) * 24))
    return s


def locator_to_latlon(loc: str) -> tuple[float, float] | None:
    loc = loc.strip()
    if len(loc) < 4:
        return None
    try:
        lon = (ord(loc[0].upper()) - 65) * 20 - 180 + int(loc[2]) * 2
        lat = (ord(loc[1].upper()) - 65) * 10 - 90 + int(loc[3])
        if len(loc) >= 6:
            lon += (ord(loc[4].lower()) - 97) / 12 + 1 / 24
            lat += (ord(loc[5].lower()) - 97) / 24 + 1 / 48
        else:
            lon += 1
            lat += 0.5
        return lat, lon
    except (ValueError, IndexError):
        return None
