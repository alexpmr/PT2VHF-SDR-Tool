# Demodulação e áudio, Tarefas de Implementação

## Pré-requisitos
- [ ] Fonte IQ com taxa múltipla de 240 kHz (ver `recepcao-sdr`)
- [ ] NumPy, SciPy e sounddevice instalados

## Tarefas

- [ ] T-01, Blocos básicos: NCO, FIR, decimador, SOS, IIR, passa-faixa complexo, de-ênfase, bloqueio de DC
  - Origem no legado: `pt2vhf/dsp/filters.py`
  - Critério de pronto: resposta em frequência conferida em teste
  - Confiança: 🟢
- [ ] T-02, Demoduladores FM, AM e SSB (com BFO para CW)
  - Origem no legado: `pt2vhf/dsp/demod.py:9-53`
  - Critério de pronto: tom de 1 kHz recuperado em cada modo
  - Confiança: 🟢
- [ ] T-03, AGC com presets e redutor de pulsos
  - Origem no legado: `pt2vhf/dsp/demod.py:55-141`
  - Critério de pronto: saída próxima ao alvo 0,3 com entrada variando 40 dB
  - Confiança: 🟢
- [ ] T-04, Squelch com histerese e cauda
  - Origem no legado: `pt2vhf/dsp/demod.py:143-167`
  - Critério de pronto: ver critério de aceitação de squelch
  - Confiança: 🟢
- [ ] T-05, `Receiver` com tabela de modos e cadeia completa
  - Origem no legado: `pt2vhf/dsp/receiver.py:13-182`
  - Critério de pronto: `process` devolve (saída, bruto) e respeita mudo e squelch
  - Confiança: 🟢
- [ ] T-06, Efeitos de áudio: EQ de 8 bandas, notch, tom, NR espectral, limitador
  - Origem no legado: `pt2vhf/dsp/audiofx.py`
  - Critério de pronto: presets aplicam os ganhos listados
  - Confiança: 🟢
- [ ] T-07, `AudioOutput` com prime, teto e contador de underruns
  - Origem no legado: `pt2vhf/audio.py:17-103`
  - Critério de pronto: sem placa de som, `available = False` e sem exceção
  - Confiança: 🟢
- [ ] T-08, Receptores extras e mistura
  - Origem no legado: `pt2vhf/engine.py:31-42,272-281,388-399`
  - Critério de pronto: limite de 4 e `in_span`
  - Confiança: 🟢
- [ ] T-09, Distribuição de áudio (`_publish_audio`, ouvintes, `audio_tap`)
  - Origem no legado: `pt2vhf/engine.py:109-121,430-436`
  - Critério de pronto: ouvinte com exceção não interrompe os outros
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Demodulação por modo com `tests/synth_signals.py` (`tests/test_dsp.py`)
- [ ] TT-02, Squelch abre, cauda e fecha
- [ ] TT-03, Taxa inválida levanta `ValueError`
- [ ] TT-04, Quinto extra recusado

## Ordem Sugerida
1. T-01 e T-02, base matemática.
2. T-03, T-04 e T-05, a cadeia do receptor.
3. T-06, efeitos.
4. T-07 a T-09, integração com a engine e a placa de som.

## Lacunas Pendentes (🔴)
- Homologar qualidade de áudio por modo com RF real.
