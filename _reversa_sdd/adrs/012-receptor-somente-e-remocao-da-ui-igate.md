# ADR 012: Receptor somente e remocao da ui igate

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.9.0 cria; v0.10.0 remove a UI)

## Contexto
Um iGate APRS envia dados à rede APRS-IS, o que contraria a natureza somente receptora do produto.

## Decisão
Na v0.9.0 o iGate foi feito RX-only (qAO, passcode do operador, sem IS→RF). Na v0.10.0 a interface e o acionamento foram removidos: nenhum envio APRS-IS pelo receptor.

## Evidência
🟢 CHANGELOG 0.10.0; `pt2vhf/aprs_igate.py:1-160`. 🟡 `aprs_igate.py` e `ui/igate_panel.py` continuam no repositório sem uso, contra o pedido do BACKLOG de não deixar componentes órfãos.

## Consequências
Produto continua só receptor; código órfão deve ser removido ou documentado como reserva.
