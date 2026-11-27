# iGate APRS, Tarefas de Implementação

> Não reimplementar o envio sem autorização explícita do mantenedor.

## Pré-requisitos
- [ ] Decisão do mantenedor sobre o futuro do código

## Tarefas

- [ ] T-01, Garantir que nenhuma tela instancia o iGate
  - Origem no legado: `pt2vhf/ui/main_window.py` (sem referência), CHANGELOG 0.10.0
  - Critério de pronto: teste que falha se `ReceiveOnlyIGate` for criado pela janela
  - Confiança: 🟢
- [ ] T-02, Remover `aprs_igate.py` e `ui/igate_panel.py` ou documentá-los como reserva
  - Origem no legado: BACKLOG P1 ("não deixar componentes órfãos")
  - Critério de pronto: decisão aplicada e testes ajustados
  - Confiança: 🔴
- [ ] T-03, (Só se reativado) filtros, qAO, fila e reconexão
  - Origem no legado: `pt2vhf/aprs_igate.py`
  - Critério de pronto: testes de `gate_line` e revisão de segurança
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, `gate_line` (`tests/test_v090_sonde_sat_igate.py`)
- [ ] TT-02, Nenhum envio a partir da UI

## Ordem Sugerida
1. T-01.
2. T-02 após decisão.
3. T-03 só com autorização.

## Lacunas Pendentes (🔴)
- Remover ou manter o código órfão.
