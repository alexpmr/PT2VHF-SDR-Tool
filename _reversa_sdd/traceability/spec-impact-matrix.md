# Spec Impact Matrix

Qual componente impacta qual feature. As 20 features vêm da organização escolhida (`granularity = feature`) e serão as pastas de spec do Redator.
Legenda: **●** núcleo da feature · **○** impacto indireto (mudar o componente pode quebrar a feature).

## Feature × componente

| Feature | sources | dsp | decoders | engine | audio/timeshift | scanner/occupancy | memory/config | traffic/sonde/sat | ai_audio | webserver | rigctl | updater | ui/main_window | ui (painéis) | i18n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| recepcao-sdr | ● | ○ | | ● | | | ○ | | | | | | ● | ○ | |
| demodulacao-e-audio | | ● | | ● | ● | | ○ | | ○ | ○ | | | ● | ○ | |
| espectro-e-waterfall | ○ | ● | | ● | | | ○ | | | ○ | | | ● | ● | |
| display-e-instrumentos | | ● | | ○ | | | ○ | | | | | | ● | ● | ○ |
| scanner-e-ocupacao | ○ | ● | | ● | | ● | ○ | | | | | ○ | ● | ● | |
| memorias-e-favoritos | | | | ○ | | ○ | ● | | | | | | ● | ● | |
| gravacao-e-timeshift | | ○ | | ● | ● | | ○ | | | | | ○ | ● | ● | |
| aprs-packet | | ○ | ● | ● | | | | ○ | | ○ | | | ○ | ● | |
| tons-dtmf-ctcss | | ○ | ● | ● | | | ○ | | | | | | ○ | ● | |
| assistente-de-sintonia | | ● | | ○ | | | | | | | | | ● | ● | |
| trafego-adsb-ais | | | | | | | ○ | ● | | | | | ○ | ● | |
| radiossonda-rs41 | ○ | ○ | | ● | | | ○ | ● | | | | | ○ | ● | |
| satelites | | | | | | | ○ | ● | | | | | ○ | ● | |
| igate-aprs | | | ○ | | | | ○ | ● | | | | | | ● | |
| reducao-de-ruido-neural | | ○ | | ● | ● | | ○ | | ● | | | | ○ | ○ | |
| legendas-e-transcricao | | | | ● | ○ | | ○ | | ● | | | | ○ | ● | |
| painel-web | | ○ | ○ | ● | | | ○ | | | ● | | | ● | | |
| cat-rigctl | | | | ○ | | | ○ | | | | ● | | ● | ● | |
| atualizacao-ota | | | | ○ | ○ | ○ | ○ | | | | | ● | ● | ● | |
| idiomas-e-configuracoes | | | | | | | ● | | | | | | ● | ● | ● |

## Componente × componente (quem quebra quem)

| Se mudar... | Impacta diretamente | Por quê |
|---|---|---|
| `sources/` | engine, ui, scanner | Contrato de blocos, `set_center_freq`, `status` |
| `dsp/` | engine, decoders, scanner, ui (S-meter, AUTO), webserver (espectro) | Demodulação, squelch, FFT, `detect_mode` |
| `decoders/` | engine, ui (painéis APRS/DTMF), aprs_map, aprs_igate | Formato de `AX25Frame`/`APRSPacket` e eventos |
| `engine.py` | ui, scanner, webserver, ai_audio, sonde_rx, OTA (`operation_busy`) | Fila de comandos, `events`, `status`, `replay_pos`, gravadores |
| `audio.py` / `timeshift.py` | engine, ui (VOX, voltar no tempo), OTA | Estados de gravação e replay adiam OTA |
| `scanner.py` | ui, occupancy, OTA | `engine.tune`, eventos de acerto |
| `config.py` | todos | Chaves e defaults; save não atômico |
| `memory.py` / presets / regiões | ui, scanner (memórias), band plan | `MemoryChannel`, `BAND_PLAN` |
| `ai_audio` | engine, ui | Filas e fallback seguro |
| `webserver.py` | ui | Autorização e defaults de chave |
| `updater.py` | ui (UpdateController), auxiliar PowerShell, site | Contrato de manifesto e de redirect |
| `ui/main_window.py` | todas as features | God object (D1) |
| `i18n.py` | ui, `apply_level` | Títulos traduzidos podem quebrar níveis (D6) |
