# APRS e packet, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `AFSKDemodulator` | `(on_frame, input_rate=48000)` | — | `process(audio)` |
| `afsk_modulate` | `(frame, sample_rate=48000, amplitude=0.5)` | `np.ndarray` | Simulador e testes |
| `AX25Frame` | `source, dest, path, info, control=0x03, pid=0xF0` | — | `path_str()`, `tnc2()` |
| `parse_frame` | `(data: bytes)` | `AX25Frame \| None` | |
| `crc16_x25` | `(data)` | `int` | |
| `HDLCDeframer` | `(on_frame)` | — | `push(bit)` |
| `parse` | `(frame)` | `APRSPacket` | Nunca levanta |
| `APRSPacket` | ver `data-dictionary.md` | — | `position_str()` |
| `distance_bearing` | `(lat1, lon1, lat2, lon2)` | `(km, graus)` | |
| `maidenhead` / `locator_to_latlon` | `(lat, lon, precision=6)` / `(loc)` | `str` / `(lat, lon) \| None` | |
| `APRSMapHistory` | `(max_stations=150, points_per_station=40)` | — | `add(...) -> bool`, `export_html(path)` |
| Evento | `("aprs", APRSPacket, ts)` | — | |

## Fluxo Principal
1. Na engine, se NFM e `decoders_enabled["aprs"]`, `afsk.process(raw)`. 🟢
2. Decimação para 9600 Hz, passa-faixa, normalização, correlação com mark e space. 🟢
3. Cada fatiador converte em bits (DPLL + NRZI) e alimenta o deframer HDLC. 🟢
4. Quadro com FCS válido → `_got` (deduplicação) → `Engine._on_ax25` → `aprs.parse` → evento `aprs`. 🟢 `engine.py:84`
5. A UI mostra o pacote, guarda no histórico do mapa e na lista web. 🟢 `ui/main_window.py:2111-2116`

## Fluxos Alternativos
- **Campo de informação vazio:** pacote só com cabeçalho. 🟢
- **Erro de índice ou valor:** texto vai para `comment`. 🟢
- **Coordenada inválida no mapa:** `add` devolve False. 🟢

## Dependências
- SciPy (`butter`), `dsp.filters` (`Decimator`, `SOSFilter`). 🟢
- Config `decoders.aprs`, `my_locator`, `my_callsign`. 🟢
- Leaflet 1.9.4 e tiles OSM no navegador. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Vários fatiadores com pesos diferentes | `decoders/afsk.py:28-31` | 🟢 |
| Decoder no áudio bruto | `dsp/receiver.py:159` | 🟢 |
| Mapa como HTML estático gerado | `aprs_map.py:38` | 🟢 |

## Estado Interno
`_dedup`, `_t`, `_hist`, fatiadores (`_phase`, `_last_sym`, `_last_bit_level`); mapa `stations` (deque por indicativo). 🟢

## Observabilidade
Mensagem "APRS: <TNC2>" na barra de status por 4 s. 🟢

## Riscos e Lacunas
- 🔴 Taxa de decodificação com RF real não medida (comparação com Dire Wolf não documentada).
- 🟡 O callsign e o locator do operador ficam no config; não devem ir para commits (CLAUDE.md).
