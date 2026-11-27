# Integrações externas

| # | Integração | Direção | Protocolo e formato | Ponto no código | Limites e segurança | Estado |
|---|---|---|---|---|---|---|
| 1 | RTL-SDR (USB) | Entrada | librtlsdr Blog ou padrão; IQ uint8 | `sources/rtlsdr_source.py` | Fila de controle, watchdog, 3 reconexões | 🟢 implementado, homologado parcialmente com V4 |
| 2 | rtl_tcp | Entrada | TCP, protocolo rtl_tcp | `sources/network_sources.py` | `SourceError` fora da faixa | 🟢 |
| 3 | SoapySDR | Entrada | Biblioteca nativa | `sources/` | Sem testes dedicados | 🟡 |
| 4 | WAV IQ / simulador | Entrada | WAV estéreo / sintético | `sources/` | — | 🟢 |
| 5 | PortAudio | Saída | sounddevice, 48 kHz | `audio.py:AudioOutput` | Prime 150 ms, teto 500 ms | 🟢 |
| 6 | dump1090/readsb | Entrada | Arquivo JSON local | `traffic.py` | JSON > 8 MB recusado | 🟢 |
| 7 | AIS NMEA | Entrada | Arquivo NMEA local | `traffic.py` | Lê só os últimos 2 MB | 🟢 |
| 8 | fsk_demod + rs41mod | Bidirecional | Pipe: IQ int16 48 kS/s → JSON | `sonde_rx.py` | 400–406 MHz; sem download automático | 🔴 RF real |
| 9 | Hamlib rigctld | Saída/entrada | TCP texto (`f`, `m`, `F`, `M`) | `rigctl.py` | Sem PTT | 🟢 |
| 10 | Painel web | Saída | HTTP GET `/`, `/state`, `/spectrum`, `/audio` (PCM 16 kHz) | `webserver.py` | Loopback livre; LAN com chave ou IP privado; sem TLS | 🟢 |
| 11 | www.pt2vhf.com | Entrada | HTTPS `update.php?product=sdr`, JSON schema 1 | `updater.py` | Host fixo, sem redirect no manifesto | 🟢 código, 🔴 campo |
| 12 | GitHub Releases | Entrada | HTTPS redirect do `download.php` | `updater.py:_PackageRedirect` | Só a release da versão; SHA-256 | 🟢 |
| 13 | Auxiliar PowerShell | Saída | Processo destacado + arquivo de resultado em `%TEMP%` | `updater.apply` | Só Windows congelado | 🟢 código, 🔴 campo |
| 14 | Modelos Whisper | Entrada | `faster_whisper.utils.download_model` | `live_caption.py:40`, `app.py:168` | Só por ação explícita; inferência offline | 🟡 origem |
| 15 | Leaflet / OSM | Saída (HTML) | HTML com unpkg.com e tile.openstreetmap.org | `aprs_map.py` | Carregado pelo navegador | 🟢 |
| 16 | libwdi (wdi-simple) | Saída | Processo elevado `runas` | `sources/rtl_driver.py` | Interface 0, um UAC | 🟢 sem testes |
| 17 | TLE de satélites | Entrada | Arquivo de texto local | `satellites.py:parse_tles` | Painel fora das abas | 🟢 |
| 18 | Exportação GPX/KML | Saída | XML | `traffic.py`, `ui/traffic_panel.py` | — | 🟢 |
| 19 | APRS-IS | Saída | TCP 14580, qAO | `aprs_igate.py` | Sem UI; órfão | 🟢 órfão |

Não há APIs REST consumidas além do manifesto OTA, nem webhooks ou filas de mensagens externas.
