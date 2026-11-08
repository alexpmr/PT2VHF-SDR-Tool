"""SGP4 satellite look angles and receive-only Doppler tracking from user TLE files.

SGP4 returns TEME; the sidereal rotation here omits nutation/polar motion,
appropriate for approximate visual tracking / amateur RX Doppler (not orbit
determination or safety-critical pointing).
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

C_KM_S = 299792.458
EARTH_W_KM = 7.2921150e-5


@dataclass(frozen=True)
class TLESatellite:
    name: str
    line1: str
    line2: str

    def satrec(self):
        try:
            from sgp4.api import Satrec
        except ImportError as exc:
            raise RuntimeError("Dependência sgp4 não instalada") from exc
        return Satrec.twoline2rv(self.line1, self.line2)


@dataclass(frozen=True)
class LookAngle:
    az_deg: float
    el_deg: float
    range_km: float
    range_rate_km_s: float


def parse_tles(content: str) -> list[TLESatellite]:
    lines = [s.strip() for s in content.splitlines()
             if s.strip() and not s.lstrip().startswith("#")]
    out: list[TLESatellite] = []
    i = 0
    while i < len(lines):
        name = "NORAD"
        if not lines[i].startswith("1 "):
            name = lines[i].removeprefix("0 ").strip() or name
            i += 1
        if i + 1 >= len(lines):
            break
        a, b = lines[i:i + 2]
        i += 2
        if not (a.startswith("1 ") and b.startswith("2 ")
                and len(a) >= 68 and len(b) >= 68
                and a[2:7] == b[2:7]):
            continue
        out.append(TLESatellite(name if name != "NORAD" else a[2:7], a, b))
    return out


def _gmst(jd: float) -> float:
    t = (jd - 2451545.0) / 36525.0
    degrees = 280.46061837 + 360.98564736629 * (jd - 2451545.0)
    degrees += 0.000387933 * t * t - (t ** 3) / 38710000.0
    return math.radians(degrees % 360.0)


def _observer(lat_deg, lon_deg, height_m):
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    a, flattening = 6378.137, 1 / 298.257223563
    ecc2 = flattening * (2 - flattening)
    n = a / math.sqrt(1 - ecc2 * math.sin(lat) ** 2)
    h = height_m / 1000.0
    return ((n + h) * math.cos(lat) * math.cos(lon),
            (n + h) * math.cos(lat) * math.sin(lon),
            (n * (1 - ecc2) + h) * math.sin(lat))


def look_angle(sat: TLESatellite, lat_deg: float, lon_deg: float, at: dt.datetime,
               height_m: float = 0) -> LookAngle:
    from sgp4.api import jday
    if not (-90 <= lat_deg <= 90 and -180 <= lon_deg <= 180):
        raise ValueError("Latitude/longitude inválidas")
    if at.tzinfo is None:
        raise ValueError("Use uma data UTC com fuso horário")
    at = at.astimezone(dt.timezone.utc)
    jd, fr = jday(at.year, at.month, at.day, at.hour, at.minute,
                  at.second + at.microsecond / 1e6)
    error, r, v = sat.satrec().sgp4(jd, fr)
    if error:
        raise ValueError(f"SGP4: erro de propagação {error}")
    angle = _gmst(jd + fr)
    co, si = math.cos(angle), math.sin(angle)
    # TEME -> ECEF (aproximação de rotação sideral; polar motion desprezado).
    x, y, z = (co * r[0] + si * r[1], -si * r[0] + co * r[1], r[2])
    vx = co * v[0] + si * v[1] + EARTH_W_KM * y
    vy = -si * v[0] + co * v[1] - EARTH_W_KM * x
    vz = v[2]
    ox, oy, oz = _observer(lat_deg, lon_deg, height_m)
    dx, dy, dz = x - ox, y - oy, z - oz
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = (-math.sin(lat) * math.cos(lon) * dx
             - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz)
    up = (math.cos(lat) * math.cos(lon) * dx
          + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz)
    az = math.degrees(math.atan2(east, north)) % 360
    el = math.degrees(math.asin(max(-1.0, min(1.0, up / d))))
    rate = (vx * dx + vy * dy + vz * dz) / d
    return LookAngle(az, el, d, rate)


def receive_doppler_hz(nominal_hz: float, radial_km_s: float) -> float:
    """Ajuste RX: aproximação não relativística; velocidade afastando = Doppler negativo."""
    if not 1000 <= nominal_hz <= 10e9 or not math.isfinite(radial_km_s):
        raise ValueError("Frequência Doppler inválida")
    return -nominal_hz * radial_km_s / C_KM_S


def next_passes(sat: TLESatellite, lat_deg: float, lon_deg: float,
                start: dt.datetime, hours=24, step_s=45, min_elevation=0) -> list[dict]:
    """Passagens aproximadas por amostragem; não retorna órbitas geométricas precisas."""
    step_s = max(5, int(step_s))
    n = min(int(float(hours) * 3600 / step_s), 20000)
    active, out = None, []
    for i in range(n + 1):
        at = start + dt.timedelta(seconds=i * step_s)
        p = look_angle(sat, lat_deg, lon_deg, at)
        if p.el_deg >= min_elevation:
            if active is None:
                active = {"aos": at, "los": at, "peak": at, "max_el": p.el_deg}
            active["los"] = at
            if p.el_deg > active["max_el"]:
                active["peak"], active["max_el"] = at, p.el_deg
        elif active is not None:
            out.append(active)
            active = None
    if active is not None:
        out.append(active)
    return out
