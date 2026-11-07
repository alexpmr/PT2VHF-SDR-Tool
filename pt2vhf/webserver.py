"""Servidor web local/LAN: replica a sessão no navegador (display, waterfall, APRS) com áudio.

Padrão dos programas PT2VHF (Sat Tool): desligado por padrão; acesso local (127.0.0.1) sem senha;
na rede local (LAN) exige a chave temporária do endereço copiado (vira cookie de sessão);
somente leitura — o navegador não altera frequência, modo nem nada no rádio.
O áudio é enviado como PCM 16 bits, 16 kHz, mono (~32 kB/s por ouvinte) e continua saindo
também no computador. HTTP na LAN não é criptografado: não exponha a porta à Internet.
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import queue
import secrets
import socket
import threading
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import numpy as np

from .dsp.filters import Decimator

AUDIO_RATE_OUT = 16_000


def detect_lan_ipv4() -> str:
    """IPv4 da interface usada para a rede (nenhum pacote é enviado)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class AudioHub:
    """Recebe o áudio a 48 kHz da thread DSP e distribui a 16 kHz para os ouvintes."""

    def __init__(self):
        self._dec = Decimator(3, cutoff=0.9)
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()

    def push(self, audio48: np.ndarray):
        with self._lock:
            if not self._clients:
                return
            clients = list(self._clients)
        a = self._dec.process(np.asarray(audio48, np.float32))
        data = (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()
        for q in clients:
            try:
                q.put_nowait(data)
            except queue.Full:  # ouvinte lento: descarta o mais antigo
                try:
                    q.get_nowait()
                    q.put_nowait(data)
                except (queue.Empty, queue.Full):
                    pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=40)
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    @property
    def listeners(self) -> int:
        with self._lock:
            return len(self._clients)


class WebServer:
    def __init__(self, state_fn, spectrum_fn, lan: bool = False, port: int = 8095):
        """state_fn() -> dict com o estado atual; spectrum_fn() -> (spec_db, center, fs) ou None.

        Ambos são chamados pelas threads HTTP: devem só ler dados já prontos (nunca tocar o Qt/rádio).
        """
        self.state_fn, self.spectrum_fn = state_fn, spectrum_fn
        self.lan, self.port = bool(lan), int(port)
        self.key = secrets.token_urlsafe(24)
        self.audio = AudioHub()
        self._httpd: ThreadingHTTPServer | None = None
        self.error = ""

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def url(self, for_lan: bool | None = None) -> str:
        lan = self.lan if for_lan is None else for_lan
        host = detect_lan_ipv4() if lan else "127.0.0.1"
        return f"http://{host}:{self.port}/" + (f"?key={self.key}" if lan else "")

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def _send(self, status, body: bytes, mime="text/plain; charset=utf-8", extra=None):
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self, qs) -> tuple[bool, dict]:
                try:
                    local = ipaddress.ip_address(self.client_address[0]).is_loopback
                except ValueError:
                    local = False
                if local:
                    return True, {}
                if not owner.lan:
                    return False, {}
                key = (qs.get("key") or [""])[0]
                if key and hmac.compare_digest(key, owner.key):
                    return True, {"Set-Cookie": f"PT2VHFSDR={owner.key}; HttpOnly; SameSite=Strict; Path=/"}
                c = SimpleCookie()
                try:
                    c.load(self.headers.get("Cookie", ""))
                except Exception:  # noqa: BLE001
                    return False, {}
                tok = c.get("PT2VHFSDR")
                return bool(tok and hmac.compare_digest(tok.value, owner.key)), {}

            def do_GET(self):
                u = urlsplit(self.path)
                ok, extra = self._authorized(parse_qs(u.query))
                if not ok:
                    self._send(HTTPStatus.FORBIDDEN, "Acesso negado: use o endereço com a chave copiado no PT2VHF SDR Tool."
                               .encode())
                    return
                if u.path == "/":
                    self._send(HTTPStatus.OK, PAGE.encode("utf-8"), "text/html; charset=utf-8", extra)
                elif u.path == "/state":
                    st = dict(owner.state_fn())
                    st["listeners"] = owner.audio.listeners
                    self._send(HTTPStatus.OK, json.dumps(st, ensure_ascii=False).encode(), "application/json")
                elif u.path == "/spectrum":
                    got = owner.spectrum_fn()
                    if got is None:
                        self._send(HTTPStatus.NO_CONTENT, b"")
                        return
                    spec, center, fs = got
                    n = len(spec)
                    k = max(1, n // 1024)
                    s = spec[:n // k * k].reshape(-1, k).max(axis=1)
                    body = json.dumps({"c": center, "fs": fs, "db": np.round(s, 1).tolist()}).encode()
                    self._send(HTTPStatus.OK, body, "application/json")
                elif u.path == "/audio":
                    self._stream_audio()
                else:
                    self._send(HTTPStatus.NOT_FOUND, b"404")

            def _stream_audio(self):
                q = owner.audio.subscribe()
                try:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("X-Audio-Format", f"s16le;rate={AUDIO_RATE_OUT};channels=1")
                    self.end_headers()
                    while owner.running:
                        try:
                            data = q.get(timeout=1.0)
                        except queue.Empty:
                            data = b"\x00\x00" * (AUDIO_RATE_OUT // 10)  # mantém a conexão viva
                        self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    owner.audio.unsubscribe(q)
                    self.close_connection = True

        host = "0.0.0.0" if self.lan else "127.0.0.1"
        self._httpd = ThreadingHTTPServer((host, self.port), Handler)
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, daemon=True, name="web").start()

    def stop(self):
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            threading.Thread(target=lambda: (httpd.shutdown(), httpd.server_close()), daemon=True).start()


PAGE = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PT2VHF SDR Tool · Web</title>
<style>
:root{color-scheme:dark;font:14px "Segoe UI",Arial,sans-serif;color:#e6ebf0;background:#11151b}
*{box-sizing:border-box}body{margin:0}header{display:flex;gap:12px;align-items:center;flex-wrap:wrap;
padding:10px 14px;background:#1b2129;border-bottom:1px solid #2e3742}header strong{color:#f0b44a}
#lcd{margin:12px;border-radius:10px;padding:12px 16px;background:linear-gradient(#f6b54a,#d9820f);color:#1c1204}
#freq{font:700 clamp(32px,7vw,64px) Consolas,monospace;letter-spacing:2px}
#tags span{display:inline-block;border:1.5px solid #1c1204;border-radius:4px;padding:1px 6px;margin-right:6px;font:700 13px Consolas,monospace}
#tags .on{background:#1c1204;color:#f6b54a}#right{float:right;text-align:right;font:700 14px Consolas,monospace}
#meter{height:12px;background:#e0a043;border-radius:3px;margin-top:8px;overflow:hidden}
#bar{height:100%;width:0;background:#1c1204;transition:width .15s}
main{padding:0 12px 12px;display:grid;gap:12px}
canvas{width:100%;display:block;background:#05070c;border-radius:6px}
.card{background:#1b2129;border:1px solid #2e3742;border-radius:8px;padding:10px}
button{background:#c9871e;color:#120c02;border:0;border-radius:5px;padding:8px 14px;font-weight:700;cursor:pointer}
table{width:100%;border-collapse:collapse}td,th{padding:5px 8px;border-bottom:1px solid #2e3742;text-align:left;white-space:nowrap}
th{color:#f0b44a}.tbl{overflow-x:auto}footer{color:#8a96a3;font-size:12px;text-align:center;padding:10px}
</style></head><body>
<header><strong>PT2VHF SDR TOOL</strong><span id="ver"></span><span style="margin-left:auto"></span>
<button id="listen">▶ Ouvir áudio</button><input id="vol" type="range" min="0" max="100" value="80" title="Volume"></header>
<section id="lcd"><div id="right"><div id="mem"></div><div id="sig"></div><div id="ctcss"></div></div>
<div id="tags"></div><div id="freq">---.---.---</div><div id="meter"><div id="bar"></div></div></section>
<main><section class="card"><canvas id="spec" height="110"></canvas><canvas id="wf" height="260"></canvas></section>
<section class="card"><b style="color:#f0b44a">APRS recebido</b><div class="tbl"><table><thead><tr><th>Hora</th><th>Indicativo</th>
<th>Tipo</th><th>Posição</th><th>Comentário</th></tr></thead><tbody id="aprs"></tbody></table></div></section></main>
<footer>Somente leitura: frequência e modo são controlados no PT2VHF SDR Tool. HTTP na rede local não é criptografado — nunca exponha esta porta à Internet. www.PT2VHF.com</footer>
<script>
const $=id=>document.getElementById(id);
function fmt(f){const s=Math.round(f).toString().padStart(10,' ');return (s.slice(0,4)+'.'+s.slice(4,7)+'.'+s.slice(7)).trim()}
async function state(){try{const r=await fetch('/state',{cache:'no-store'});const s=await r.json();
$('ver').textContent='v'+s.version;$('freq').textContent=fmt(s.freq);
$('tags').innerHTML=['<span class="on">'+s.mode+'</span>','<span>BW '+(s.bw/1000).toFixed(1)+'k</span>',
s.sq_open?'<span class="on">BUSY</span>':'',s.scan?'<span class="on">SCAN</span>':'',s.replay?'<span class="on">REPLAY</span>':''].join('');
$('mem').textContent=s.mem||'';$('sig').textContent=s.s_text+'  '+s.dbm.toFixed(1)+' dBm';$('ctcss').textContent=s.ctcss?('CTCSS '+s.ctcss):'';
$('bar').style.width=Math.max(0,Math.min(100,(s.dbm+147)/114*100))+'%';
$('aprs').innerHTML=(s.aprs||[]).map(a=>'<tr><td>'+a.t+'</td><td>'+a.src+'</td><td>'+a.type+'</td><td>'+a.pos+'</td><td>'+a.text+'</td></tr>').join('');
}catch(e){}}
setInterval(state,400);state();
const sc=$('spec'),wc=$('wf'),sx=sc.getContext('2d'),wx=wc.getContext('2d');
function color(v){const t=Math.max(0,Math.min(1,v));const st=[[0,0,0,0],[.15,0,0,80],[.35,0,60,200],[.55,0,200,220],[.72,240,240,0],[.88,255,110,0],[1,255,0,0]];
for(let i=1;i<st.length;i++)if(t<=st[i][0]){const a=st[i-1],b=st[i],k=(t-a[0])/(b[0]-a[0]);return[a[1]+(b[1]-a[1])*k,a[2]+(b[2]-a[2])*k,a[3]+(b[3]-a[3])*k]}return[255,0,0]}
let lo=-110,hi=-40;
async function spec(){try{const r=await fetch('/spectrum',{cache:'no-store'});if(r.status!==200)return;const d=await r.json();const v=d.db;
const W=v.length;if(wc.width!==W){wc.width=W;sc.width=W}const sorted=[...v].sort((a,b)=>a-b);const fl=sorted[Math.floor(v.length*.2)];lo=lo*.9+(fl-8)*.1;hi=hi*.9+(Math.max(sorted[Math.floor(v.length*.998)]+8,fl+30))*.1;
sx.fillStyle='#05070c';sx.fillRect(0,0,W,sc.height);sx.strokeStyle='#ffe680';sx.beginPath();
v.forEach((y,i)=>{const yy=sc.height-(y-lo)/(hi-lo+5)*sc.height;i?sx.lineTo(i,yy):sx.moveTo(i,yy)});sx.stroke();
const img=wx.getImageData(0,0,W,wc.height);wx.putImageData(img,0,1);const row=wx.createImageData(W,1);
v.forEach((y,i)=>{const c=color((y-lo)/(hi-lo));row.data.set([c[0],c[1],c[2],255],i*4)});wx.putImageData(row,0,0);}catch(e){}}
setInterval(spec,120);
let ctx=null,gain=null,next=0,reader=null;
$('vol').oninput=()=>{if(gain)gain.gain.value=$('vol').value/100};
$('listen').onclick=async()=>{if(ctx){ctx.close();ctx=null;if(reader)reader.cancel();$('listen').textContent='▶ Ouvir áudio';return}
ctx=new AudioContext();gain=ctx.createGain();gain.gain.value=$('vol').value/100;gain.connect(ctx.destination);next=0;
$('listen').textContent='■ Parar áudio';const r=await fetch('/audio',{cache:'no-store'});reader=r.body.getReader();let rest=new Uint8Array(0);
while(ctx){const {value,done}=await reader.read();if(done)break;let buf=new Uint8Array(rest.length+value.length);buf.set(rest);buf.set(value,rest.length);
const n=Math.floor(buf.length/2);rest=buf.slice(n*2);if(!n)continue;const pcm=new Int16Array(buf.buffer.slice(0,n*2));
const ab=ctx.createBuffer(1,n,16000);const ch=ab.getChannelData(0);for(let i=0;i<n;i++)ch[i]=pcm[i]/32768;
const src=ctx.createBufferSource();src.buffer=ab;src.connect(gain);const now=ctx.currentTime;
if(next<now+0.05||next>now+1.0)next=now+0.25;src.start(next);next+=ab.duration}};
</script></body></html>"""
