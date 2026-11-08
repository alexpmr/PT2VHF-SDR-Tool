"""Mapa de estações APRS recebido pelo SDR, exportado como HTML Leaflet.

Sem transmissão ou iGate: só mostra pacotes com posição decodificados localmente.
O HTML usa tiles OSM/Leaflet na Internet; não envia o conteúdo APRS ao servidor.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from pathlib import Path


class APRSMapHistory:
    def __init__(self, max_stations=150, points_per_station=40):
        self.max_stations = max_stations
        self.points_per_station = points_per_station
        self.stations = {}

    def add(self, source, lat, lon, timestamp=None, comment=""):
        try:
            lat, lon = float(lat), float(lon)
        except (ValueError, TypeError):
            return False
        if not (math.isfinite(lat) and math.isfinite(lon) and
                -90 <= lat <= 90 and -180 <= lon <= 180):
            return False
        source = str(source or "???").strip()[:20]
        when = time.time() if timestamp is None else float(timestamp)
        if source not in self.stations and len(self.stations) >= self.max_stations:
            oldest = min(self.stations, key=lambda s: self.stations[s][-1]["time"])
            del self.stations[oldest]
        self.stations.setdefault(source, deque(maxlen=self.points_per_station)).append({
            "lat": lat, "lon": lon, "time": when, "comment": str(comment or "")[:120]})
        return True

    def export_html(self, path: str | Path):
        points = [{"source": src, "track": list(track)} for src, track in self.stations.items()]
        # JSON dentro de <script>: escape de separadores e caracteres que fecham o elemento.
        safe = json.dumps(points, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        html = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PT2VHF SDR Tool · Mapa APRS recebido</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{margin:0;height:100%;font-family:Arial,sans-serif}
#note{position:fixed;top:10px;right:12px;z-index:999;background:#fff;padding:8px;border-radius:5px;
box-shadow:0 1px 8px #5558;font-size:12px;max-width:300px}</style></head><body>
<div id="map"></div><div id="note">PT2VHF SDR Tool · Apenas APRS recebido. Atualize a página para ver novos pacotes.
Mapa requer acesso aos tiles OpenStreetMap.</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>const received = __DATA__;
function clean(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
if(typeof L !== "undefined"){
const map = L.map("map").setView([-15.78,-47.93],5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{
maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
const all = [], colors=["#d84343","#2986c5","#5ca44a","#b0852f","#824eb6"];
received.forEach((entry,i)=>{const points=entry.track.map(p=>[p.lat,p.lon]);
if(!points.length)return;const last=entry.track[entry.track.length-1];all.push(...points);
if(points.length>1)L.polyline(points,{color:colors[i%colors.length],weight:2,opacity:.75}).addTo(map);
const date=new Date(last.time*1000).toLocaleString("pt-BR");
L.circleMarker([last.lat,last.lon],{radius:6,color:colors[i%colors.length],fillOpacity:.9})
.addTo(map).bindPopup("<b>"+clean(entry.source)+"</b><p>"+clean(last.comment)+"</p>"+clean(date));
});
if(all.length)map.fitBounds(L.latLngBounds(all).pad(.14),{maxZoom:13});
} else {document.getElementById("note").textContent="Leaflet indisponível: verifique a Internet.";}
</script></body></html>"""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html.replace("__DATA__", safe), encoding="utf-8")
        return out
