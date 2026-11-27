# Espectro e waterfall, Tarefas de Implementação

## Pré-requisitos
- [ ] Engine entregando blocos (ver `demodulacao-e-audio`)
- [ ] pyqtgraph disponível

## Tarefas

- [ ] T-01, `compute_spectrum` com janela em cache e média de quadros
  - Origem no legado: `pt2vhf/dsp/receiver.py:183-210`
  - Critério de pronto: tom em +100 kHz aparece no bin certo
  - Confiança: 🟢
- [ ] T-02, Produção de linhas na engine por `wf_speed`
  - Origem no legado: `pt2vhf/engine.py:349-356`
  - Critério de pronto: 20 linhas/s com `wf_speed = 20`
  - Confiança: 🟢
- [ ] T-03, Widget com espectro, cascata, eixo em MHz e paletas
  - Origem no legado: `pt2vhf/ui/waterfall.py:19-130`
  - Critério de pronto: 6 paletas e eixo legível
  - Confiança: 🟢
- [ ] T-04, `add_line` com redução, deslocamento de histórico, média e pico
  - Origem no legado: `pt2vhf/ui/waterfall.py:219-284`
  - Critério de pronto: mudança de centro desloca as colunas
  - Confiança: 🟢
- [ ] T-05, Clique, duplo clique, arraste da banda passante e pan
  - Origem no legado: `pt2vhf/ui/waterfall.py:287-400`, `pt2vhf/ui/main_window.py:1635-1712`
  - Critério de pronto: `tests/test_waterfall_click_to_tune.py` passa
  - Confiança: 🟢
- [ ] T-06, Níveis manual e automático, atalho Ctrl+L
  - Origem no legado: `pt2vhf/ui/waterfall.py:133-149`, `ui/main_window.py:684,1984`
  - Critério de pronto: percentis aplicados
  - Confiança: 🟢
- [ ] T-07, Auto de níveis contínuo (backlog)
  - Origem no legado: não existe; pedido registrado na memória do projeto
  - Critério de pronto: ligado, o piso acompanha o ruído sem tela preta acima de 800 MHz
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Clique dentro e fora do IQ (`tests/test_waterfall_click_to_tune.py`)
- [ ] TT-02, Duplo clique com sintonia recusada
- [ ] TT-03, Deslocamento de histórico ao mudar o centro

## Ordem Sugerida
1. T-01 e T-02 (dados).
2. T-03 e T-04 (desenho).
3. T-05 e T-06 (interação).
4. T-07 só com aprovação do backlog.

## Lacunas Pendentes (🔴)
- Definir o comportamento do Auto contínuo (frequência de atualização, histerese).
