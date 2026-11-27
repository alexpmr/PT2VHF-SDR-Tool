# Tons DTMF e CTCSS, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `goertzel_power` | `(x, freqs, fs)` | `np.ndarray` | Potência por frequência |
| `DTMFDecoder` | `(on_digit, input_rate=48000)` | — | `process(audio)` |
| `CTCSSDetector` | `(input_rate=48000, window_s=1.0)` | — | `process(audio) -> float \| None`, `tone`, `level` |
| `Engine.tone_squelch` | `float \| None` | — | Hz configurado |
| `Engine.status["ctcss"]` | `float \| None` | — | Tom medido |
| Evento | `("dtmf", tecla, ts)` | — | |

## Fluxo Principal
1. Em NFM, CTCSS processa o áudio bruto e atualiza `status["ctcss"]`. 🟢
2. Se `tone_squelch`, compara com o medido (tolerância 1 Hz) e zera o áudio se não conferir. 🟢
3. DTMF processa o áudio bruto e emite dígitos por evento. 🟢

## Fluxos Alternativos
- **Fora de NFM:** CTCSS = None e DTMF não roda. 🟢
- **Janela incompleta:** devolve o último tom. 🟢

## Dependências
- `dsp.filters.Decimator`. 🟢
- Config `decoders.dtmf`, `decoders.ctcss`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Goertzel nas frequências de interesse | `decoders/tones.py:24-35` | 🟢 |
| Dígito exige 2 quadros iguais | `decoders/tones.py:70-78` | 🟢 |

## Estado Interno
DTMF: `_buf`, `_last`, `_count`, `_emitted`. CTCSS: `_buf`, `tone`, `level`. 🟢

## Observabilidade
Lista de DTMF no painel; tom medido no painel e na memória. 🟢

## Riscos e Lacunas
- 🔴 DCS (código digital) não é suportado.
