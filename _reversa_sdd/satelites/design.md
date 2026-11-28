# Satélites, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `TLESatellite` | `name, line1, line2` (imutável) | — | `satrec()` |
| `parse_tles` | `(content: str)` | `list[TLESatellite]` | |
| `look_angle` | `(sat, lat_deg, lon_deg, at: datetime, height_m=0)` | `LookAngle` | `at` com fuso |
| `LookAngle` | `az_deg, el_deg, range_km, range_rate_km_s` | — | |
| `receive_doppler_hz` | `(nominal_hz, radial_km_s)` | `float` Hz | |
| `next_passes` | `(sat, lat, lon, start, hours=24, step_s=45, min_elevation=0)` | `list[dict]` | `aos, los, peak, max_el` |
| `SatellitePanel` | `(cfg)` | — | Sinal `tuneReceiveRequested(float)`; `refresh`, `calculate_passes` |

## Fluxo Principal
1. O operador abre um TLE; o painel lista os satélites. 🟢
2. O timer do painel chama `refresh`: posição do locator, `look_angle`, `receive_doppler_hz`, texto de resumo. 🟢
3. Com seguimento ligado e elevação > 0, emite `tuneReceiveRequested(f_corrigida)` → `MainWindow.tune`. 🟢
4. `calculate_passes` preenche a tabela com horários locais. 🟢

## Fluxos Alternativos
- **Sem TLE carregado:** "Carregue um arquivo TLE." 🟢
- **Sem passagens:** "Sem passagens acima do horizonte nas próximas 24 h." 🟢

## Dependências
- `sgp4` (≥ 2.23). 🟢
- `locator_to_latlon` do módulo APRS. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| SGP4 local com TLE do operador (v0.9.0) | `satellites.py`, CHANGELOG | 🟢 |
| Rotação sideral simplificada | `satellites.py:94-99` | 🟢 |
| Previsão por amostragem | `satellites.py:121-141` | 🟢 |

## Estado Interno
Lista de satélites carregados, `_last_freq`, timer; config `sat_tle_path`, `sat_nominal_hz`, `sat_doppler_auto`, `my_locator`. 🟢

## Observabilidade
Texto de resumo no painel. 🟢

## Riscos e Lacunas
- 🟢 Painel inacessível na UI atual: `SatellitePanel` é criado e ligado a `tune`, mas não entra em nenhuma aba (`ui/main_window.py:272,618`) [Revisão: 🟡→🟢].
- 🟡 Passo de 45 s pode errar AOS/LOS em até 45 s.
