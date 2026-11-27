# Tráfego ADS-B e AIS

## Visão Geral
Mostra aeronaves (ADS-B), navios (AIS) e radiossondas de telemetria externa a partir de **arquivos gerados por decodificadores externos** (readsb/dump1090, rtl_ais/AIS-catcher, radiosonde_auto_rx), com tabela, mapa e exportação CSV/GPX/KML. Não demodula ADS-B nem AIS do IQ. 🟢

## Responsabilidades
- Ler `aircraft.json` (ADS-B), log NMEA VDM (AIS) e JSON de sondas. 🟢
- Converter unidades e validar coordenadas. 🟢
- Decodificar AIS tipos 1/2/3/18/19 (posição) e 5 (nome). 🟢
- Atualizar manual ou automaticamente a cada 5 s. 🟢
- Exportar CSV, mapa HTML, GPX e KML. 🟢

## Regras de Negócio
- Nenhuma conexão a servidores públicos e nenhum software externo é executado; só arquivos locais. 🟢 `traffic.py:1-6,248-249`
- ADS-B: velocidade em nós → km/h (×1,852), altitude em pés → metros (×0,3048), preferindo `alt_geom` a `alt_baro`; descarta aeronaves sem posição, com `seen_pos` < 0 ou > 120 s, ou com `hex` vazio ou > 12 caracteres; carimbo = `now − seen_pos`. 🟢 `traffic.py:55-88`
- Sondas: aceita `{sondes}`, `{telemetry}`, objeto único ou lista; campos alternativos (`lat`/`latitude`, `id`/`serial`/`sonde_id`, `vel_v`/`ascent_rate` etc.); fase subida se vertical > 0,3 m/s, descida se < −0,3. 🟢 `traffic.py:91-133`
- AIS: aceita `!AIVDM`, `!AIVDO`, `!BSVDM`; checksum NMEA verificado; mensagens em até 9 fragmentos; mais de 100 fragmentos pendentes zera o buffer; velocidade 1023 e rumo 3600 = indisponível; posição fora de ±181°/±91° descartada. 🟢 `traffic.py:161-238`
- AIS lê só os últimos 2 MB do arquivo (descarta a 1ª linha parcial); JSON maior que 8 MB é recusado com orientação para rotacionar o arquivo. 🟢 `traffic.py:248-271`
- `Track` valida coordenadas (finitas e dentro dos limites). 🟢 `traffic.py:22-44`
- O painel guarda até 5000 posições de histórico. 🟢 `ui/traffic_panel.py:130`
- Mapa HTML usa Leaflet 1.9.4 (unpkg) e tiles OSM; texto escapado; GPX e KML com escape XML. 🟢 `traffic.py:282-360`
- `TrafficFeedsPanel` (painel agrupado) existe mas não está ligado à janela; os painéis em uso são `SourceTab` ADS-B, AIS e Sonda. 🟢 `ui/traffic_panel.py:191`, `ui/main_window.py:159-173`
- Pedidos do backlog: decodificadores ADS-B (1090 MHz) e ACARS (131,550/131,725/131,825 MHz AM) embarcados. A memória do projeto registra modos embarcados publicados na v1.0.7, mas **não existem nesta branch** (v0.13.3). 🔴

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Ler ADS-B de `aircraft.json` | Must | Aeronaves com posição listadas |
| RF-02 | Ler AIS de log NMEA | Must | Navios com nome após tipo 5 |
| RF-03 | Ler telemetria de sondas | Should | Sondas com fase |
| RF-04 | Atualização automática de 5 s | Should | `traffic_<tipo>_auto` |
| RF-05 | Exportar CSV, mapa, GPX, KML | Should | Arquivos válidos |
| RF-06 | Mensagens de erro de arquivo | Must | Arquivo ausente ou inválido mostra o motivo |
| RF-07 | ADS-B/ACARS nativos | Could | Fora desta branch 🔴 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Responsividade | Lê só a cauda de 2 MB do AIS | `traffic.py:253-262` | 🟢 |
| Limite | JSON até 8 MB | `traffic.py:263-264` | 🟢 |
| Privacidade | Nenhuma conexão externa | `traffic.py:5` | 🟢 |
| Segurança | Escape HTML/XML nas exportações | `traffic.py:282-360` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um aircraft.json com uma aeronave a 35000 pés e 450 nós
Quando o painel ADS-B atualiza
Então aparece altitude 10668 m e velocidade 833,4 km/h

Dado uma aeronave com seen_pos 300
Quando o arquivo é lido
Então ela não aparece

Dado uma linha AIS com checksum errado
Quando o log é lido
Então ela é ignorada

Dado um JSON de 9 MB
Quando o painel tenta ler
Então aparece "JSON maior que 8 MB: configure rotação no decodificador externo"
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Leitura ADS-B e AIS | Must | Núcleo |
| Sondas externas, exportação, auto | Should | Complementos |
| Decoders nativos | Could | Backlog |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/traffic.py` | `Track`, `parse_adsb`, `parse_radiosondes`, `AISDecoder`, `parse_ais`, `load_traffic`, `export_csv`, `export_map`, `export_gpx`, `export_kml` | 🟢 |
| `pt2vhf/ui/traffic_panel.py` | `SourceTab`, `TrafficFeedsPanel` (órfão) | 🟢 |
| `pt2vhf/ui/main_window.py` | `adsb_panel`, `ais_panel`, `sonde_feed` | 🟢 |
