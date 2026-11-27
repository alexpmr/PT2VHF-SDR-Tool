# Dicionário de dados — PT2VHF-SDR-Tool

> Gerado pelo **Arqueólogo** (Reversa) em 2026-11-27. Não há banco de dados: as entidades são dataclasses/objetos em memória e arquivos JSON/CSV/WAV. 🟢 salvo indicação.

## Entidades de domínio

### `MemoryChannel` (`memory.py`)
| Campo | Tipo | Obrig. | Padrão | Observação |
|-------|------|--------|--------|------------|
| name | str | sim | — | nome exibido; exportado com até 16 caracteres no CHIRP |
| freq | float (Hz) | sim | — | |
| mode | str | não | `NFM` | um de `MODES` |
| bandwidth | float (Hz) | não | 12000 | |
| category | str | não | `Simplex` | categoria nova é criada ao adicionar |
| squelch | float \| None | não | None | dBFS |
| ctcss | float \| None | não | None | Hz |
| offset | float (Hz) | não | 0 | repetidora, informativo; sinal = duplex |
| notes | str | não | "" | |
| favorite | bool | não | False | barra de favoritos |
| skip_scan | bool | não | False | `Skip = S` no CHIRP |
| id | str | não | uuid4 hex[:10] | |
| band (propriedade) | str | — | — | `band_for(freq)` ou "Fora de banda" |

### `Band` (`memory.py`)
`name`, `start`, `end` (Hz), `mode`, `step` (Hz), `service` (padrão "Radioamador").

### `PresetPack` (`presets.py`)
`key`, `name`, `category`, `description`, `channels: list[MemoryChannel]`.

### `ModeInfo` (`dsp/receiver.py`)
`name`, `low`, `high` (Hz relativos à portadora), `step` (Hz), `bw_presets` (tupla de larguras).

### `ModeGuess` (`dsp/assist.py`)
`mode`, `bandwidth`, `center_offset` (Hz a somar ao VFO), `confidence` (0–1), `reason` (texto).

### `AX25Frame` (`decoders/ax25.py`)
| Campo | Tipo | Padrão |
|-------|------|--------|
| source | str | — |
| dest | str | — |
| path | list[str] | [] (`*` = repetido) |
| info | bytes | b"" |
| control | int | 0x03 (UI) |
| pid | int | 0xF0 (sem camada 3) |

### `APRSPacket` (`decoders/aprs.py`)
| Campo | Tipo | Observação |
|-------|------|------------|
| source, dest, path, raw | str | `raw` = TNC2 |
| type | str | Posição, Clima, Mic-E, Status, Mensagem, Telemetria (def.), Telemetria, Objeto, Terceiros, Outro |
| lat, lon | float \| None | graus decimais (S/W negativos) |
| symbol | str | tabela + código |
| comment | str | |
| speed_kmh | float \| None | |
| course | int \| None | graus |
| altitude_m | float \| None | |
| message_to, message | str | mensagens/objetos |
| telemetry | dict | `seq`, `A1..A5`, `bits` |
| weather | dict | `dir_vento`, `vel_vento_mph`, `rajada_mph`, `temp_F`, `temp_C`, `umidade`, `pressao_dPa`, `chuva_1h` |

### `Track` (`traffic.py`)
| Campo | Tipo | Observação |
|-------|------|------------|
| source | str | `ADS-B`, `AIS`, `Sonda` |
| ident | str | ICAO hex, MMSI, serial |
| lat, lon | float | validados (finito e dentro dos limites) |
| label | str | voo, nome do navio, serial |
| altitude_m | float \| None | |
| speed_kmh | float \| None | |
| course_deg | float \| None | |
| vertical_ms | float \| None | sondas |
| timestamp | float (epoch) | padrão agora |
| details | str | texto livre |

### `ScanRange` / `ScannerConfig` / `Hit` / `Detection` (`scanner.py`)
- `ScanRange`: `name`, `start`, `end`, `resolution` (Hz), `mode`, `bandwidth`, `snr_db` (10), `notes`.
- `ScannerConfig`: `start`, `end`, `resolution` (5000), `snr_db` (10), `mode` (NFM), `bandwidth` (12000), `listen` (False), `dwell_lines` (4), `settle_lines` (2), `resume_s` (2), `max_listen_s` (0 = sem limite), `cooldown_s` (8), `priority_freq` (None), `priority_interval_s` (3), `lockouts` (set).
- `Hit`: `freq`, `first_seen`, `last_seen`, `hits` (1), `max_snr`, `max_db` (−200), `seconds_active`, `listened`.
- `Detection`: `freq`, `level_db`, `snr_db`.

### `TLESatellite` / `LookAngle` (`satellites.py`)
- `TLESatellite`: `name`, `line1`, `line2` (imutável).
- `LookAngle`: `az_deg`, `el_deg`, `range_km`, `range_rate_km_s`.

### `UpdateInfo` (`updater.py`)
`version`, `date`, `notes`, `page`, `file` (dict `kind`, `name`, `url`, `size`, `sha256` ou None), `allow_test_host`, `unavailable_reason`.

### `UsbInterface` (`sources/rtl_driver.py`)
`instance_id`, `pid`, `mi` (None se não composto), `service`, `status`, `name`; propriedades `radio_interface` (MI 0 ou None) e `ready` (serviço WinUSB/libusb).

### Evento do motor (`engine.events`)
Tupla `(tipo: str, dado, timestamp: float)`. Tipos e dados:

| Tipo | Dado | Origem |
|------|------|--------|
| aprs | APRSPacket | decoder AFSK |
| dtmf | str (tecla) | decoder DTMF |
| activity / vox | dict `file, freq, mode, start, peak_db, duration` | ActivityRecorder |
| replay | float (s atrás) | timeshift |
| replay_end | 0.0 | timeshift |
| source_msg | str | RtlSdrSource |
| error | str | loop DSP |
| neural_error | str | RNNoise |
| auto_mode / auto_tune / assist_* | dict `res, vfo, gen` ou similar | assistente (UI) |
| live_caption | tupla `(ts, texto, indicativos, idioma, (vfo, modo))` | legendas |
| caption_error | str | legendas |
| transcription | tupla `(caminho, texto, indicativos)` | Transcriber |
| sonde_rx / sonde_frame / sonde_status | `(Track, json)` / json / str | RS41 |

### `Engine.status` (dict)
`signal_db` (dBFS do canal), `signal_sample_time` (monotônico), `sq_open`, `ctcss` (Hz ou None), `dropped`, `cpu` (fração do tempo real), `running`, `audio_level` (pico 0–1).

## Arquivos persistidos

| Arquivo | Local | Formato | Escrita |
|---------|-------|---------|---------|
| `config.json` | diretório de config | dict plano (ver `DEFAULTS` em `config.py`) | não atômica |
| `memorias.json` | idem | `{categories: [], channels: [MemoryChannel]}` | não atômica |
| regiões (caminho definido pela UI) | idem | `{regions: {nome: {categories, channels}}}` | atômica |
| `ocupacao_24h.json` | idem | `{schema: 1, bin_hz: 12500, hours: {epoch_hora: {freq_bin: n}}}` | atômica, ≤ 1×/20 s |
| `mapa_aprs_recebido.html` | idem | HTML Leaflet | sobrescreve |
| `models/whisper-<tamanho>/` | idem | modelo CTranslate2 (`model.bin`, `config.json`) | download explícito |
| `pt2vhf-sdr.log` | idem | log texto | só sem console |
| `PT2VHF_<data>_<hora>_<Hz>Hz_AF.wav` | pasta de gravações | WAV 48 kHz mono 16 bits | contínua |
| `PT2VHF_<data>_<hora>_<Hz>Hz_IQ.wav` | idem | WAV estéreo 16 bits (I/Q) | contínua |
| `<AAAA-MM-DD>/HHMMSS_<f>MHz_<modo>[_VOX][_n].wav` | idem | WAV 48 kHz mono | por transmissão ou sessão |
| captura RS41 | escolhido pelo usuário | int16 LE I/Q intercalado, 48 kS/s, 1–60 s | única |
| `PT2VHF-SDR-Tool-update-result.txt` | `%TEMP%` | 3 linhas: status, versão, detalhe | escrito pelo auxiliar, apagado após leitura |
| `pt2vhf-sdr-selftest.log` | `%TEMP%` | texto | a cada autoteste |
| QSettings `PT2VHF/SDRTool` | registro/ini do Qt | `geometry`, `split_v05`, `audio_panel` | Qt |

## Chaves de configuração (`DEFAULTS`) agrupadas

| Grupo | Chaves |
|-------|--------|
| Fonte | `source`, `device_index`, `device_name`, `rtl_tcp_host`, `rtl_tcp_port`, `soapy_args`, `sample_rate`, `center_freq`, `gain`, `ppm`, `bias_tee`, `direct_sampling`, `reconnect_on_start`, `rx_was_on`, `rx_ever_connected` (+ `rtl_library` fora dos padrões) |
| Sintonia | `vfo_freq`, `vfo_b_freq`, `mode`, `bandwidth`, `step`, `band_stacks`, `bands_visible` (+ `auto_mode`, `auto_tune` fora dos padrões) |
| Áudio | `volume`, `squelch`, `agc`, `agc_speed`, `nb`, `nr`, `neural_audio`, `neural_strength`, `eq_enabled`, `eq_gains`, `wfm_deemph_us`, `audio_device` (+ `vox`) |
| Waterfall/display | `fft_size`, `wf_min_db`, `wf_max_db`, `wf_colormap`, `wf_speed`, `spectrum_avg`, `wf_keep_vfo_centered`, `lcd_theme`, `lcd_scale_percent`, `ui_level`, `analog_enabled`, `analog_style`, `presentation`, `presentation_minimal` |
| Medição | `s_meter_cal` |
| Estação | `my_locator`, `my_callsign` |
| Decoders | `decoders` (`aprs`, `dtmf`, `ctcss`) |
| Scanner/gravação | `scan_dwell_ms`, `scan_resume_s`, `timeshift_s`, `recordings_dir` |
| IA | `live_caption_model`, `live_caption_language`, `live_caption_enabled` |
| Integrações | `cat_host`, `cat_port`, `cat_auto_sync`, `traffic_<tipo>_path`, `traffic_<tipo>_auto`, `web_require_key` (+ `web_enabled`, `web_allow_lan`, `web_port`, `igate_host`, `igate_port`) |
| OTA | `check_updates` |

Chaves marcadas "+" são gravadas pela UI sem estarem em `DEFAULTS` 🟢.
