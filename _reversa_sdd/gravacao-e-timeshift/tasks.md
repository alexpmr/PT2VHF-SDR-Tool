# Gravação e timeshift, Tarefas de Implementação

## Pré-requisitos
- [ ] Receiver com `rec_audio_raw` e squelch (ver `demodulacao-e-audio`)
- [ ] `recordings_dir` configurável

## Tarefas

- [ ] T-01, `WavRecorder` mono e estéreo I/Q
  - Origem no legado: `pt2vhf/audio.py:105-131`
  - Critério de pronto: arquivo legível com taxa e canais certos
  - Confiança: 🟢
- [ ] T-02, Gravação contínua de áudio e IQ na engine, com nomes padronizados
  - Origem no legado: `pt2vhf/engine.py:290-324`
  - Critério de pronto: nomes conforme `requirements.md`
  - Confiança: 🟢
- [ ] T-03, `ActivityRecorder` com pré-gravação, cauda, mínimo, máximo e sessão única
  - Origem no legado: `pt2vhf/audio.py:134-240`
  - Critério de pronto: critérios de aceitação de VOX
  - Confiança: 🟢
- [ ] T-04, IQ VOX
  - Origem no legado: `pt2vhf/engine.py:340-342,423-427`
  - Critério de pronto: IQ só com squelch aberto + 1,5 s
  - Confiança: 🟢
- [ ] T-05, `TimeShiftBuffer` circular com centros
  - Origem no legado: `pt2vhf/timeshift.py`
  - Critério de pronto: leitura com volta do índice e centro certo
  - Confiança: 🟢
- [ ] T-06, Replay na engine e retorno ao vivo
  - Origem no legado: `pt2vhf/engine.py:236-269,359-375`
  - Critério de pronto: eventos `replay` e `replay_end`
  - Confiança: 🟢
- [ ] T-07, UI: botões, VOX pronto, atividade, TimeShiftBox
  - Origem no legado: `pt2vhf/ui/main_window.py:1127-1180,1415-1435`, `ui/assist_panels.py:58-88`
  - Critério de pronto: botões refletem o estado
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, VOX e atividade com áudio sintético (`tests/test_v030_features.py`, `tests/test_v040_tuning.py`)
- [ ] TT-02, Timeshift ida e volta
- [ ] TT-03, Gravar com receptor desligado é recusado

## Ordem Sugerida
1. T-01 e T-02.
2. T-03 e T-04.
3. T-05 e T-06.
4. T-07.

## Lacunas Pendentes (🔴)
- Definir se há limite de espaço em disco ou rotação de arquivos.
