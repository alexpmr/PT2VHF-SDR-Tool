# Satélites, Tarefas de Implementação

## Pré-requisitos
- [ ] `sgp4` instalado
- [ ] Locator do operador (sem publicar coordenadas pessoais)

## Tarefas

- [ ] T-01, `parse_tles` com 2 e 3 linhas
  - Origem no legado: `pt2vhf/satellites.py:39-56`
  - Critério de pronto: NORADs diferentes nas linhas 1 e 2 são descartados
  - Confiança: 🟢
- [ ] T-02, `look_angle` (TEME→ECEF, observador WGS-84, ENU)
  - Origem no legado: `pt2vhf/satellites.py:59-111`
  - Critério de pronto: comparação com referência com erro < 1°
  - Confiança: 🟢
- [ ] T-03, `receive_doppler_hz`
  - Origem no legado: `pt2vhf/satellites.py:114-118`
  - Critério de pronto: sinal do desvio conforme aproximação/afastamento
  - Confiança: 🟢
- [ ] T-04, `next_passes`
  - Origem no legado: `pt2vhf/satellites.py:121-141`
  - Critério de pronto: passagem com AOS < pico < LOS
  - Confiança: 🟢
- [ ] T-05, `SatellitePanel` e ligação à sintonia
  - Origem no legado: `pt2vhf/ui/satellite_panel.py`, `ui/main_window.py:272,618`
  - Critério de pronto: seguimento respeita o horizonte
  - Confiança: 🟢
- [ ] T-06, Decidir onde o painel aparece na UI
  - Origem no legado: aba removida (CLAUDE.md)
  - Critério de pronto: decisão do mantenedor
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Biblioteca orbital (`tests/test_v090_sonde_sat_igate.py`)
- [ ] TT-02, Doppler com velocidade conhecida

## Ordem Sugerida
1. T-01 a T-04.
2. T-05.
3. T-06 após decisão.

## Lacunas Pendentes (🔴)
- Painel fora das abas: reintroduzir, mover para Ferramentas ou remover.
