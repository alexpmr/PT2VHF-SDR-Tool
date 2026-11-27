# Tons DTMF e CTCSS, Tarefas de Implementação

## Pré-requisitos
- [ ] Áudio bruto NFM (ver `demodulacao-e-audio`)

## Tarefas

- [ ] T-01, `goertzel_power`
  - Origem no legado: `pt2vhf/decoders/tones.py:24-35`
  - Critério de pronto: potência máxima no tom gerado
  - Confiança: 🟢
- [ ] T-02, `DTMFDecoder` com limiares de energia, pureza e twist
  - Origem no legado: `pt2vhf/decoders/tones.py:38-78`
  - Critério de pronto: 16 teclas reconhecidas; twist de 10 dB rejeitado
  - Confiança: 🟢
- [ ] T-03, `CTCSSDetector`
  - Origem no legado: `pt2vhf/decoders/tones.py:81-115`
  - Critério de pronto: 51 tons distinguidos
  - Confiança: 🟢
- [ ] T-04, Tone squelch na engine
  - Origem no legado: `pt2vhf/engine.py:400-412`
  - Critério de pronto: critérios de aceitação
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, DTMF e CTCSS sintéticos (`tests/test_decoders.py`)
- [ ] TT-02, Tone squelch com tom errado

## Ordem Sugerida
1. T-01, T-02, T-03.
2. T-04.

## Lacunas Pendentes (🔴)
- Decidir se DCS entra no escopo.
