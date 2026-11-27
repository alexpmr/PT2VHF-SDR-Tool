# Gravação e timeshift, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `WavRecorder` | `(path, rate, channels)` | — | `write(x)`, `close()`, `samples`, `started` |
| `ActivityRecorder` | `(folder, rate=48000, tail_s=1.5, min_s=1.0, max_s=300.0, preroll_s=0.5, single_file=False)` | — | |
| `ActivityRecorder.process` | `(audio, opened, freq, mode, level_db)` | `dict \| None` | Evento ao fechar |
| `ActivityRecorder.close` | `()` | `dict \| None` | |
| `ActivityRecorder.active` / `session_path` | propriedades | `bool` / `Path \| None` | |
| `Engine.start_audio_recording` / `start_iq_recording` | `(folder)` | `Path` | |
| `Engine.stop_audio_recording` / `stop_iq_recording` | `()` | — | |
| `Engine.activity_rec`, `vox_rec`, `iq_vox` | atributos | — | Definidos pela UI |
| `TimeShiftBuffer` | `(sample_rate, seconds)` | — | `append`, `read(pos, n)`, `oldest`, `center_at`, `written`, `megabytes`, `available_seconds` |
| `Engine.set_timeshift` / `start_replay` / `stop_replay` | `(seconds)` / `(seconds_back)` / `()` | — | Via `call` |
| `TimeShiftBox` sinais | `bufferChanged(float)`, `replayRequested(float)`, `liveRequested()` | — | |
| Eventos | `activity`, `vox` (dict), `replay` (s atrás), `replay_end` | — | |

Evento de transmissão: `{file, freq, mode, start, peak_db, duration}`. 🟢

## Fluxo Principal
1. Cada bloco: IQ gravado (se ativo e VOX permitir) antes da demodulação. 🟢 `engine.py:339-342`
2. Timeshift recebe o bloco e o centro. 🟢 `engine.py:359-361`
3. Em replay, o Receiver processa o IQ lido do buffer com offset do centro antigo. 🟢 `engine.py:363-375`
4. `_publish_audio` escreve no gravador contínuo. 🟢 `engine.py:118-120`
5. `activity_rec` e `vox_rec` recebem `rec_audio_raw` e o estado `opened`; eventos vão para `engine.events`. 🟢 `engine.py:428-432`

## Fluxos Alternativos
- **Duas transmissões no mesmo segundo:** sufixo `_2`, `_3`. 🟢 `audio.py:172-175`
- **Bloco maior que o buffer:** só a cauda é guardada. 🟢 `timeshift.py:39-42`
- **Replay pedido sem dados:** ignorado. 🟢 `engine.py:250-251`
- **Desligar VOX com transmissão aberta:** `close()` fecha e emite o evento final ao painel. 🟢 `ui/main_window.py:1156-1159`

## Dependências
- `wave`, NumPy. 🟢
- Squelch e tone squelch (`demodulacao-e-audio`, `tons-dtmf-ctcss`). 🟢
- Config `recordings_dir`, `timeshift_s`, `vox`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Timeshift em IQ, não em áudio, para reouvir qualquer frequência da faixa (ADR 005) | `timeshift.py`, `assist_panels.py:58` | 🟢 |
| Quantização int8 | `timeshift.py:17,36-38` | 🟢 |
| Pré-gravação usa áudio sem squelch | `dsp/receiver.py:176` | 🟢 |

## Estado Interno
Gravadores: `_audio_rec`, `_iq_rec`, `_iq_open_until`, `activity_rec`, `vox_rec`. Activity: `_pre`, `_pre_n`, `_rec`, `_session`, `_closed_for`, `_tx_samples`, `_info`. Timeshift: `_buf`, `_centers`, `written`, `replay_pos`. Estados em `state-machines.md` §4 e §5. 🟢

## Observabilidade
Mensagens na barra de status com o caminho; flags `REC` no LCD; eventos na lista de atividade. 🟢

## Riscos e Lacunas
- 🟡 int8 reduz a faixa dinâmica do replay.
- 🟡 Nenhum limite de espaço em disco para gravação contínua.
