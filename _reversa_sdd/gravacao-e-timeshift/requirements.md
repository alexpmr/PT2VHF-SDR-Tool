# Gravação e timeshift

## Visão Geral
Grava áudio e IQ em WAV (contínuo ou por VOX), grava transmissões por atividade em arquivos separados e permite "voltar no tempo" para reouvir os últimos segundos de qualquer frequência da faixa capturada. 🟢

## Responsabilidades
- Gravação contínua de áudio (48 kHz mono) e de IQ (estéreo I/Q na taxa da fonte). 🟢
- Gravação VOX de áudio (por transmissão ou num arquivo de sessão) e IQ só com squelch aberto. 🟢
- Gravação por atividade com eventos listados no painel. 🟢
- Buffer de timeshift com replay de 10 ou 30 s e retorno ao vivo. 🟢

## Regras de Negócio
- Gravar exige receptor ligado; senão o botão volta a desligado. 🟢 `ui/main_window.py:1140-1143,1164-1167`
- VOX exige squelch ativo (> −150 dBFS) ou tone squelch; senão pergunta se deve ajustar o squelch automaticamente (6 dB acima do ruído). 🟢 `ui/main_window.py:1127-1136`
- Gravação por atividade com squelch aberto aplica o squelch automático sem perguntar. 🟢 `ui/main_window.py:1421-1423`
- Pasta base `recordings_dir` (padrão `~/PT2VHF-Gravacoes`); VOX em `vox/`, atividade em `atividade/`. 🟢 `config.py:90`, `ui/main_window.py:1148,1423`
- Nomes: `PT2VHF_AAAAMMDD_HHMMSS_<VFO>Hz_AF.wav` e `..._<centro>Hz_IQ.wav`; por transmissão `<AAAA-MM-DD>/HHMMSS_<f>MHz_<modo>[_VOX][_n].wav`. 🟢 `engine.py:291-309`, `audio.py:168-176`
- WAV PCM 16 bits, valores limitados a ±1. 🟢 `audio.py:105-131`
- Áudio gravado independe de volume e mudo. 🟢 `dsp/receiver.py:176-178`
- `ActivityRecorder`: pré-gravação 0,5 s, cauda 1,5 s, mínimo 1 s (VOX manual usa 0,5 s), máximo 300 s; mudança de frequência > 1 Hz fecha a transmissão; curta demais é apagada (modo por arquivo) ou só não gera evento (sessão única). A duração do evento não conta a pré-gravação nem a cauda. 🟢 `audio.py:134-240`, `ui/main_window.py:1150`
- O squelch conta como aberto para gravação só se estiver ativo e aberto e o tone squelch confere. 🟢 `engine.py:423-425`
- IQ VOX grava enquanto o squelch está aberto e até 1,5 s depois. 🟢 `engine.py:340-342,426-427`
- Timeshift: buffer IQ int8 (2 bytes por amostra), opções Desligado, 10, 20 (padrão), 30 e 60 s; ~48 MB para 20 s a 1,2 MS/s. 🟢 `timeshift.py`, `ui/assist_panels.py:58-88`, `config.py:82`
- O buffer guarda o centro de cada trecho, então o replay acompanha retunes do passado. 🟢 `timeshift.py:30-36,70-78`
- Replay: posição = escrito − segundos × taxa, nunca antes do mais antigo; ao alcançar o presente volta ao vivo sozinho (`replay_end`). 🟢 `engine.py:247-262,363-372`
- Mudar o tamanho do buffer apaga o conteúdo e sai do replay. 🟢 `engine.py:236-245`
- O OTA é adiado durante gravação ou replay. 🟢 `ui/main_window.py:1441-1453`

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Gravar áudio contínuo | Must | WAV 48 kHz mono criado |
| RF-02 | Gravar IQ contínuo | Must | WAV estéreo na taxa da fonte |
| RF-03 | VOX de áudio por transmissão ou sessão | Should | Um arquivo por transmissão ou um só |
| RF-04 | IQ VOX | Should | Só trechos com squelch aberto + 1,5 s |
| RF-05 | Gravação por atividade com lista de eventos | Should | Evento com arquivo, frequência, modo, início, pico e duração |
| RF-06 | Timeshift com replay de 10/30 s e ao vivo | Should | Áudio do passado e volta automática |
| RF-07 | Escolher tamanho do buffer | Should | 0, 10, 20, 30, 60 s |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Concorrência | Gravadores trocados sob `_lock` entre UI e DSP | `engine.py:291-316` | 🟢 |
| Memória | Timeshift com 2 bytes por amostra | `timeshift.py:17` | 🟢 |
| Privacidade | Gravações só locais; não publicar sem consentimento | CLAUDE.md | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o receptor ligado com squelch em -80 dBFS
Quando uma transmissão de 3 s acontece com VOX por arquivo
Então surge um WAV de cerca de 5 s (0,5 s antes + 3 s + 1,5 s de cauda) e um evento de 3 s

Dado uma transmissão de 0,4 s com mínimo de 1 s
Quando ela termina
Então o arquivo é apagado e nenhum evento é gerado

Dado o squelch aberto em -150 dBFS
Quando o operador liga o VOX e recusa o ajuste automático
Então a gravação não começa

Dado 20 s de timeshift cheios
Quando o operador aperta "⏪ 10 s"
Então o áudio volta 10 s e, ao alcançar o presente, o status volta a "Ao vivo"

Dado o receptor desligado
Quando o operador liga a gravação de áudio
Então o botão volta a desligado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Gravação de áudio e IQ | Must | Recurso básico |
| VOX e atividade | Should | Economia de espaço |
| Timeshift | Should | Diferencial, com fallback ao vivo |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/audio.py` | `WavRecorder`, `ActivityRecorder` | 🟢 |
| `pt2vhf/timeshift.py` | `TimeShiftBuffer` | 🟢 |
| `pt2vhf/engine.py` | `start/stop_audio_recording`, `start/stop_iq_recording`, `set_timeshift`, `start_replay`, `stop_replay`, `replay_seconds_behind`, `process_block` | 🟢 |
| `pt2vhf/ui/assist_panels.py` | `TimeShiftBox` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_vox_ready`, `_record_audio`, `_record_iq`, `_auto_record`, `_rec_flag` | 🟢 |
