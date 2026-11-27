# Radiossonda RS41, Tarefas de Implementação

## Pré-requisitos
- [ ] `fsk_demod` e `rs41mod` compilados do radiosonde_auto_rx
- [ ] Fonte IQ física ou gravação IQ ≥ 96 kS/s
- [ ] Engine com `iq_listeners`

## Tarefas

- [ ] T-01, `find_binary` e `build_decoder_commands`
  - Origem no legado: `pt2vhf/sonde_rx.py:29-51`
  - Critério de pronto: faixa e PATH validados
  - Confiança: 🟢
- [ ] T-02, `ChannelIQ` com fase contínua nos dois caminhos de reamostragem
  - Origem no legado: `pt2vhf/sonde_rx.py:53-110`
  - Critério de pronto: tom em f_sonda sai em 0 Hz sem saltos de fase entre blocos
  - Confiança: 🟢
- [ ] T-03, `RS41Receiver` com fila, threads, pipes e diagnóstico
  - Origem no legado: `pt2vhf/sonde_rx.py:113-335`
  - Critério de pronto: processos falsos (eco de JSON) produzem eventos
  - Confiança: 🟢
- [ ] T-04, Captura IQ de diagnóstico
  - Origem no legado: `pt2vhf/sonde_rx.py:291-317`
  - Critério de pronto: arquivo de 20 s = 3 840 000 bytes
  - Confiança: 🟢
- [ ] T-05, Integração na UI e validações
  - Origem no legado: `pt2vhf/ui/main_window.py:1468-1520`, `ui/sonde_decoder_panel.py`
  - Critério de pronto: mensagens dos critérios de aceitação
  - Confiança: 🟢
- [ ] T-06, Corrigir a docstring do módulo (FI +12 kHz → 0 Hz)
  - Origem no legado: `pt2vhf/sonde_rx.py:3`
  - Critério de pronto: docstring coerente com `SIGNAL_OFFSET_HZ`
  - Confiança: 🟢
- [ ] T-07, Homologação com RF real
  - Origem no legado: BACKLOG P0, CLAUDE.md
  - Critério de pronto: captura IQ real + serial, quadro, posição e altitude no mapa
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Canalização e comandos (`tests/test_v090_sonde_sat_igate.py`)
- [ ] TT-02, Pipeline com binários simulados
- [ ] TT-03, Replay de captura IQ real com quadros conhecidos (falta a captura) 🔴

## Ordem Sugerida
1. T-01 e T-02.
2. T-03 e T-04.
3. T-05 e T-06.
4. T-07 antes de declarar a feature funcional.

## Lacunas Pendentes (🔴)
Ver `questions.md`.
