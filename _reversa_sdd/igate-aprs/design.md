# iGate APRS, Design Técnico

> Código remanescente, sem uso na UI desde a v0.10.0.

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `clean_call` | `(value)` | `str` | `ValueError` se inválido |
| `gate_line` | `(raw: str, gate_call: str)` | `str \| None` | TNC2 → APRS-IS qAO |
| `ReceiveOnlyIGate` | `(callsign, passcode, host="rotate.aprs2.net", port=14580, software_version="0.9.0", on_status=None)` | — | |
| `start` / `stop` | `()` | — | Thread `pt2vhf-igate` |
| `submit` | `(raw)` | `bool` | Enfileirado ou descartado |
| Contadores | `sent`, `dropped`, `verified` | — | |

## Fluxo Principal
1. `submit` converte com `gate_line`, deduplica (45 s) e enfileira. 🟢
2. A thread conecta, faz login, espera `logresp verified` e envia a fila linha a linha. 🟢
3. Máquina de estados em `state-machines.md` §9. 🟢

## Fluxos Alternativos
- **Recusa de login:** status e nova tentativa após 15 s. 🟢
- **Erro de socket:** status "APRS-IS indisponível" e nova tentativa após 5 s. 🟢

## Dependências
`socket`, `threading`, `queue`, `re`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| RX-only com qAO (v0.9.0) | `aprs_igate.py:3` | 🟢 |
| Remoção da UI (v0.10.0, ADR 012) | CHANGELOG | 🟢 |

## Estado Interno
`_queue`, `_seen`, `_stop`, `_thread`, `verified`, `sent`, `dropped`. 🟢

## Observabilidade
`on_status` com mensagens de conexão. 🟢

## Riscos e Lacunas
- 🟡 Código de envio presente, embora desligado: superfície que pode ser religada por engano.
- 🔴 Decisão pendente: remover os arquivos ou mantê-los como reserva documentada.
