# Scanner e ocupação, Tarefas de Implementação

## Pré-requisitos
- [ ] Engine com linhas de espectro e `hold_center` (ver `espectro-e-waterfall`, `recepcao-sdr`)
- [ ] MemoryBank (ver `memorias-e-favoritos`)

## Tarefas

- [ ] T-01, `detect_signals` e `level_at`
  - Origem no legado: `pt2vhf/scanner.py:58-108`
  - Critério de pronto: sinal sintético detectado no centróide; DC ignorado
  - Confiança: 🟢
- [ ] T-02, Cálculo de segmentos e máquina de estados do scanner
  - Origem no legado: `pt2vhf/scanner.py:140-330`
  - Critério de pronto: transições de `state-machines.md` §2
  - Confiança: 🟢
- [ ] T-03, Acertos, lockout, cooldown e prioridade
  - Origem no legado: `pt2vhf/scanner.py:183-325`
  - Critério de pronto: critérios de aceitação de lockout e cooldown
  - Confiança: 🟢
- [ ] T-04, Presets de faixa
  - Origem no legado: `pt2vhf/scanner.py:21-37`
  - Critério de pronto: 15 presets
  - Confiança: 🟢
- [ ] T-05, Varredura de memórias e de faixa com squelch automático
  - Origem no legado: `pt2vhf/ui/main_window.py:1034-1300`
  - Critério de pronto: espera dwell, segura no squelch aberto, retoma após `resume`
  - Confiança: 🟢
- [ ] T-06, `OccupancyHistory` com deduplicação por minuto e gravação atômica
  - Origem no legado: `pt2vhf/occupancy.py`
  - Critério de pronto: arquivo `schema 1`, janela de 24 h
  - Confiança: 🟢
- [ ] T-07, Painel de ocupação e ligação com os acertos
  - Origem no legado: `pt2vhf/ui/occupancy_panel.py`, `ui/main_window.py:2053-2069`
  - Critério de pronto: atualiza a cada 4 s
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Scanner com sinais sintéticos (`tests/test_scanner_presets.py`)
- [ ] TT-02, Ocupação (`tests/test_v070_features.py`)
- [ ] TT-03, Varredura de memórias com squelch simulado

## Ordem Sugerida
1. T-01, núcleo de detecção.
2. T-02 e T-03.
3. T-06, independente.
4. T-04, T-05 e T-07, integração com a UI.

## Lacunas Pendentes (🔴)
- Decidir se o squelch automático deve usar a mediana, como diz o comentário.
