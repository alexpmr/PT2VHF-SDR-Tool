# Assistente de sintonia, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `Engine.capture_if` | `(seconds, callback(iq, fs))` | — | IF de 240 kHz; callback numa thread |
| `detect_mode` | `(iq, fs, freq_hz=None)` | `ModeGuess \| None` | |
| `ModeGuess` | `mode, bandwidth, center_offset, confidence, reason` | — | |
| `fine_tune` | `(iq, fs, mode, vfo, step=0.0, search_hz=None)` | `(delta_hz, motivo) \| None` | |
| `estimate_ssb_offset` | `(iq, fs, sideband="USB", max_offset=600.0)` | `(delta, confiança) \| None` | |
| `adaptive_passband` | `(iq, fs, mode, low, high)` | `(low, high) \| None` | |
| `occupied_band` | `(iq, fs, search_hz=120000, thresh_db=12.0)` | `(lo, hi, piso) \| None` | |
| `AssistBox` sinais | `autotuneRequested()`, `detectRequested()`, `filterRequested()` | — | |
| Eventos | `auto_mode`, `auto_tune` com `{res, vfo, gen}` | — | |

## Fluxo Principal
1. Seleção de transmissão (clique, memória, scanner) chama `_after_select`. 🟢
2. Incrementa `_sel_gen`, agenda `capture_if` em 250 ms. 🟢
3. A engine junta `last_if` até o total e dispara o callback em thread. 🟢 `engine.py:377-386`
4. O callback roda `detect_mode` ou `fine_tune` e põe o resultado em `engine.events`. 🟢
5. O tick entrega a `_auto_result`, que valida geração e VFO e aplica. 🟢

## Fluxos Alternativos
- **Sem sinal ou voz insuficiente:** `None`, nada muda. 🟢
- **Exceção na análise:** registrada como aviso, resultado None. 🟢 `ui/main_window.py:1662-1664`
- **Espectro de centro anterior no vizinho:** tenta de novo em 150 ms. 🟢

## Dependências
- SciPy (`firwin`, `lfilter`, `welch`/PSD), NumPy. 🟢
- Scanner (`detect_signals`) para o vizinho. 🟢
- Config `auto_mode`, `auto_tune` (gravadas fora de `DEFAULTS`). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Atuar no VFO, não no áudio (ADR 004) | `dsp/assist.py:6` | 🟢 |
| SSB pelos harmônicos da voz acumulados no tempo | `dsp/assist.py:3-6` | 🟢 |
| Contador de geração contra resultados obsoletos | `ui/main_window.py:1647,1669` | 🟢 |

## Estado Interno
`_sel_gen`, `auto_mode`, `auto_tune`, `_neighbor_hops`; na engine, `_capture` e `rx.keep_if`. 🟢

## Observabilidade
Mensagens na barra de status com o motivo ("AUTO: NFM — envoltória constante…"). 🟢

## Riscos e Lacunas
- 🔴 Taxa de acerto do AUTO com RF real não medida.
- 🟡 O classificador IQ do PR #2 é experimental e não faz parte desta feature.
