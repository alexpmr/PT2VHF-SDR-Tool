# Assistente de sintonia, Tarefas de Implementação

## Pré-requisitos
- [ ] Engine com `capture_if` e `keep_if` no Receiver
- [ ] `detect_signals` do scanner

## Tarefas

- [ ] T-01, `occupied_band` e PSD
  - Origem no legado: `pt2vhf/dsp/assist.py:130-166`
  - Critério de pronto: bordas de um sinal sintético com erro < 1 bin
  - Confiança: 🟢
- [ ] T-02, `detect_mode` com a árvore de decisão
  - Origem no legado: `pt2vhf/dsp/assist.py:184-236`
  - Critério de pronto: cada modo sintético classificado com a confiança listada
  - Confiança: 🟢
- [ ] T-03, `estimate_ssb_offset` e `fine_tune`
  - Origem no legado: `pt2vhf/dsp/assist.py:29-120,260-310`
  - Critério de pronto: erro de 200 Hz estimado com tolerância de 20 Hz
  - Confiança: 🟢
- [ ] T-04, `adaptive_passband`
  - Origem no legado: `pt2vhf/dsp/assist.py:239-257`
  - Critério de pronto: limites por modo
  - Confiança: 🟢
- [ ] T-05, Captura de IF na engine
  - Origem no legado: `pt2vhf/engine.py:283-289,377-386`
  - Critério de pronto: callback recebe `seconds × 240000` amostras
  - Confiança: 🟢
- [ ] T-06, Orquestração na UI com geração e limiares
  - Origem no legado: `pt2vhf/ui/main_window.py:1644-1698`
  - Critério de pronto: resultado obsoleto descartado
  - Confiança: 🟢
- [ ] T-07, Transmissão vizinha
  - Origem no legado: `pt2vhf/ui/main_window.py:1715-1745`
  - Critério de pronto: respeita lockouts e distância mínima
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Classificação e sintonia fina (`tests/test_assist.py`)
- [ ] TT-02, Resultado obsoleto descartado
- [ ] TT-03, Vizinho sem sinal mantém o VFO

## Ordem Sugerida
1. T-01 a T-04, algoritmos puros.
2. T-05.
3. T-06 e T-07.

## Lacunas Pendentes (🔴)
- Medir acerto do AUTO com RF real antes de recomendar como padrão.
