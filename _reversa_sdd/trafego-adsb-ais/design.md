# Tráfego ADS-B e AIS, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `Track` | `source, ident, lat, lon, label="", altitude_m, speed_kmh, course_deg, vertical_ms, timestamp, details` | — | Valida coordenadas |
| `parse_adsb` | `(data: dict, now=None)` | `list[Track]` | `ValueError` se não for objeto |
| `parse_radiosondes` | `(data, now=None)` | `list[Track]` | |
| `AISDecoder.ingest` | `(line, now=None)` | `Track \| None` | Guarda `names` e `tracks` |
| `parse_ais` | `(lines: str, now=None)` | `list[Track]` | |
| `load_traffic` | `(path, kind: "ADS-B" \| "AIS" \| "Sonda")` | `list[Track]` | `FileNotFoundError`, `ValueError` |
| `export_csv` / `export_map` / `export_gpx` / `export_kml` | `(tracks, path)` | — | |
| `SourceTab` | `(kind, cfg)` | — | `refresh(force)`, `add_live_record(record)`, `open_map()` |

## Fluxo Principal
1. O operador escolhe o arquivo do decodificador externo (`traffic_<tipo>_path`). 🟢
2. `refresh` chama `load_traffic`; erros de arquivo aparecem no painel. 🟢 `ui/traffic_panel.py:101-130`
3. Os registros preenchem a tabela e o histórico (até 5000). 🟢
4. Com auto ligado, repete a cada 5 s. 🟢
5. Exportações sob demanda. 🟢

## Fluxos Alternativos
- **Arquivo grande de AIS:** só a cauda. 🟢
- **Mensagem AIS fragmentada:** junta fragmentos pela chave (sentença, id, canal, contagem). 🟢
- **RS41 interno:** `sonde_feed.add_live_record` recebe registros do `RS41Receiver` (ver `radiossonda-rs41`). 🟢

## Dependências
- `json`, `csv`, `html`, `xml.sax.saxutils`. 🟢
- Leaflet/OSM no navegador. 🟢
- Decodificadores externos instalados pelo operador. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Tráfego só por arquivos externos (ADR 009) | `traffic.py:1-6` | 🟢 |
| Decodificador AIS próprio sobre NMEA | `traffic.py:161-238` | 🟢 |

## Estado Interno
`AISDecoder.fragments`, `names`, `tracks`; `SourceTab.history`; config `traffic_<tipo>_path` e `traffic_<tipo>_auto`. 🟢

## Observabilidade
Texto de status no painel com contagem e erro. 🟢

## Riscos e Lacunas
- 🟡 `TrafficFeedsPanel` órfão.
- 🔴 Divergência entre a memória do projeto (modos embarcados v1.0.7) e esta branch.
